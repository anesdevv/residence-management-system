# RÉSIVO Desktop — Session Persistence & Security Architecture

This document describes the design, security guarantees, lifecycle, and threat model of the **"Stay signed in until this PC restarts"** capability in the RÉSIVO desktop application.

---

## 1. Executive Summary

RÉSIVO allows university housing staff and administrators to stay signed in across application restarts without re-entering credentials. However, unlike traditional web browsers or mobile apps that persist sessions indefinitely, RÉSIVO enforces a strict Windows-aligned boundary: **sessions automatically terminate when Windows restarts, shuts down, or the operator signs out of Windows.**

Key Guarantees:
- **Zero Password Storage**: Passwords are *never* persisted to disk, cached in memory, or logged. Only ephemeral GoTrue OAuth tokens (`access_token` and `refresh_token`) are retained.
- **Hardware & Account-Bound Encryption**: Session data is encrypted using Windows Data Protection API (**DPAPI**) scoped to the current Windows user account and bound with app-specific cryptographic entropy.
- **Logon Session Binding**: The session is cryptographically bound to the current Windows Logon Session LUID (`AuthenticationId`). When the operator signs out of Windows or restarts the machine, the logon session ID is invalidated, causing RÉSIVO to securely purge the session.
- **Fail-Closed Security**: Any ambiguity (missing token information, altered boot timestamp, corrupted ciphertext, tamper detection) results in immediate zero-fill wipe and fallback to the login screen.
- **Single Token Owner**: `SessionManager` coordinates token refresh listeners, preventing race conditions during Supabase token rotation.

---

## 2. Architecture & How It Works

```
                     +---------------------------------------+
                     |           Operator Login              |
                     |  "Stay signed in until PC restarts"   |
                     +-------------------+-------------------+
                                         |
                                         v
                    +--------------------+--------------------+
                    |        Supabase GoTrue Auth Response    |
                    | (access_token, refresh_token, user_id)  |
                    +--------------------+--------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
             [Setting: UNCHECKED]                 [Setting: CHECKED]
                       |                                   |
                       v                                   v
             Zero disk storage.                   Query Windows OS:
             Memory-only session.                 1. TokenStatistics (LUID)
                                                  2. Boot Epoch (GetTickCount64)
                                                           |
                                                           v
                                                  Construct Payload (v1)
                                                           |
                                                           v
                                                  DPAPI CryptProtectData
                                                  + App Entropy (SHA-256)
                                                           |
                                                           v
                                                  Atomic Safe Write:
                                                  %LOCALAPPDATA%/RESIVO/session/session.bin
```

### 2.1 Session Token vs. Password
- **The operator's password is never stored on disk.** It exists only in memory during the instantaneous authentication call to Supabase and is immediately overwritten.
- Persisted state contains only:
  - `access_token`: Short-lived Supabase JWT (1 hour lifetime).
  - `refresh_token`: Opaque string used by Supabase Auth to rotate tokens.
  - `user_id`: UUID of the authenticated staff member.
  - `created_at` / `last_refreshed_at`: Epoch timestamps.
  - `logon_session_id`: Windows authentication LUID.
  - `boot_epoch`: Estimated system boot timestamp.
  - `schema_version` / `version`: Structural version integer (`1`).

### 2.2 Windows DPAPI Protection
- On Windows systems, encryption and decryption are performed via `CryptProtectData` and `CryptUnprotectData` in `Crypt32.dll`.
- **Current User Scope**: The encryption key is derived by Windows from the logged-in user's credentials and system master keys (`CRYPTPROTECT_UI_FORBIDDEN`). No other Windows user account (even an Administrator) can decrypt the file on that machine.
- **Application Entropy Constant**: To prevent other programs running under the same user account from trivially invoking DPAPI to read RÉSIVO session files, an application-specific cryptographic entropy constant (`SESSION_ENTROPY`) is passed to `pOptionalEntropy`.
- Non-Windows environments and unit tests fall back to `FakeBackend` with HMAC-SHA256 authenticated encryption.

### 2.3 Windows Logon Session Binding
- Every time a user logs into Windows, the Local Security Authority (LSA) creates a unique 64-bit Locally Unique Identifier (**LUID**) for that logon session.
- RÉSIVO inspects the process token via:
  ```c
  OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken);
  GetTokenInformation(hToken, TokenStatistics, &stats, sizeof(stats), &retLen);
  // stats.AuthenticationId -> HighPart:LowPart
  ```
- This LUID remains constant while the user is logged into Windows. The moment the user logs off, locks out of a temporary session, shuts down, or restarts Windows, the LUID is permanently discarded by the Windows kernel.
- On subsequent app launches, RÉSIVO checks if `stored_logon == current_logon`. If the logon ID has changed, the session file is immediately zero-wiped and discarded.

### 2.4 Boot Epoch Fallback (Fast Startup Protection)
- In scenarios where Windows Fast Startup (hybrid hibernation) is enabled or TokenStatistics is unavailable, RÉSIVO computes the system boot epoch using `GetTickCount64()`:
  $$\text{boot\_epoch} = \text{time.time}() - \frac{\text{uptime\_ms}}{1000.0}$$
- A tolerance threshold of $\pm 300\text{ seconds}$ (5 minutes) accounts for clock drift. If the calculated boot epoch deviates by more than 5 minutes from the stored epoch, RÉSIVO recognizes that the operating system was rebooted and discards the session.

### 2.5 Fail-Closed Security Policy
If any of the following occur during session loading:
1. File missing, empty, or unreadable $\rightarrow$ Return to login.
2. Decryption failure (tampered bytes or different Windows user) $\rightarrow$ Zero-wipe, return to login.
3. Payload JSON malformed or schema version mismatch $\rightarrow$ Zero-wipe, return to login.
4. Missing required token fields $\rightarrow$ Zero-wipe, return to login.
5. Logon session mismatch $\rightarrow$ Zero-wipe, return to login with "reboot" banner.
6. Boot epoch drift $> 300\text{ s}$ $\rightarrow$ Zero-wipe, return to login with "reboot" banner.
7. Inability to verify logon continuity $\rightarrow$ Zero-wipe, return to login.
8. Maximum age exceeded ($> 7\text{ days}$) $\rightarrow$ Zero-wipe, return to login with "expired" banner.

### 2.6 Absolute Maximum Lifetime
Even if a PC is left running continuously without a reboot, the session is subject to an absolute ceiling:
$$\text{SESSION\_MAX\_AGE\_HOURS} = 168 \quad (7\text{ days})$$
When a stored session's age exceeds 168 hours, RÉSIVO purges the session file and prompts for fresh credentials.

### 2.7 Single Token Owner & Race Prevention
Supabase tokens automatically refresh during operation. If multiple threads or concurrent requests attempted to write updated tokens simultaneously, file corruption or token synchronization errors could occur.
- `SessionManager` hooks into Supabase's `on_auth_state_change` (`TOKEN_REFRESHED`).
- All disk write operations in `SessionStore` are protected by a re-entrant thread lock (`threading.RLock`).
- Writes use atomic temporary files (`session_<uuid>.tmp`), followed by `os.fsync` and `os.replace` to guarantee atomicity.

---

## 3. Session Lifecycle Matrix

| Event / Scenario | Stored Session State | Behavior on Launch / Event |
|---|---|---|
| **Close app with X / Alt+F4** | **Kept** | Next launch enters `MainWindow` directly without login. |
| **Kill process in Task Manager** | **Kept** | Next launch enters `MainWindow` directly without login. |
| **Minimize to system tray** | **Kept** | App stays active in background; restores immediately. |
| **Lock screen / Sleep / Wake** | **Kept** | Session persists; resumes without prompting. |
| **Temporary network disconnect** | **Kept** | Amber reconnecting banner; resumes when network returns. |
| **Operator clicks "Sign out"** | **Purged** | Session file zero-wiped; returns to login screen. |
| **Setting toggled OFF in Settings**| **Purged** | Session file zero-wiped immediately. |
| **Windows Restart or Shut Down** | **Purged** | Next launch displays: *"You were signed out because Windows restarted."* |
| **Windows User Sign-out / Switch** | **Purged** | Logon LUID mismatch; file purged; reboot banner displayed. |
| **7 Days Pass (168 hours)** | **Purged** | Max-age check fails; file purged; *"Your session has expired."* |
| **Password changed on another PC** | **Purged** | Supabase rejects refresh token; file purged; expiry banner displayed. |

---

## 4. Threat Model & Security Notes

### 4.1 Cross-User Access on Shared PC
- **Threat**: Another user logs into their own Windows account on the same PC and attempts to open RÉSIVO or inspect the session file.
- **Defense**: Windows DPAPI prevents any other Windows user account from decrypting the file. Even an administrator on the machine cannot unprotect the data without the user's password or private master keys.

### 4.2 Shared Windows Account (Multiple Physical Users)
- **Threat**: Multiple staff members share a single generic Windows account (e.g., `reception-desk`).
- **Mitigation / Advice**:
  - Operators should uncheck *"Stay signed in until this PC restarts"* on shared accounts.
  - When finishing a shift, operators should click **Sign out** (available in the sidebar footer and in **Settings $\rightarrow$ Security & Sign-in**).

### 4.3 Malware in the Same User Context
- Any software running with the privileges of the logged-in user can invoke DPAPI functions.
- To raise the difficulty of generic credential dumpers, RÉSIVO enforces application-specific entropy (`SESSION_ENTROPY`).
- Because session tokens are bound to the active logon session and have a 7-day hard expiration, stolen session tokens cannot outlive the Windows session on the target machine.

---

## 5. Manual Session Wipe (Operator Emergency Procedure)

If an operator wishes to manually purge all stored authentication data from disk:

1. Close RÉSIVO.
2. Press `Win + R`, paste:
   ```cmd
   explorer %LOCALAPPDATA%\RESIVO\session
   ```
   (or `%APPDATA%\RESIVO\session`)
3. Delete the `session.bin` file (and any `.tmp` files).
4. Launch RÉSIVO — the application will prompt for credentials.
