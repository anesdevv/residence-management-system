# macOS cleanup notes

Read only the sections relevant to the candidates under consideration. Commands below are inspection examples, not authorization to mutate their targets.

## Space accounting and audit records

- Start with `df -k /System/Volumes/Data`. Use the actual home/data volume when that path is absent. Record exact free bytes before and after batches with `shutil.disk_usage` or equivalent.
- Use `du -x -k -d 1` to locate large directories without traversing other filesystems. Broaden progressively rather than repeatedly traversing the entire home directory.
- APFS clones and snapshots can share blocks. Hundreds of GB of Chrome copies or simulator directories may release almost no unique storage. Keep allocated size, logical size, and measured free-space change separate. Overlapping scan roots also must not be summed.
- `~/Library/Developer/CoreDevice/DeviceFS` can be a mounted virtual view of device/simulator files. Check `df`, `mount`, and filesystem IDs; do not count it as an independent local cache or delete through it.
- File creation/modification dates support attribution, not an exact historical ledger. Compare prior inventories and free-space readings. Concurrent jobs can consume gains during cleanup.
- Use a new private audit directory, with manifests and configuration/lockfile hashes outside Git repositories. Avoid collecting file contents, secrets, full process environments, or unredacted command lines.

## Active-use checks

Inspect `ps -axo pid=,ppid=,comm=` first. When needed, inspect process arguments privately for candidate paths and operation types; arguments can contain secrets. Include native apps, IDEs, language/build processes, automation/test runners, emulators, and processes launched from candidate/cache paths.

Query relevant PIDs with `lsof -nP -p <comma-separated-pids> -Fpcn`, using adequate output capacity and a bounded timeout. Global `lsof` or recursive `lsof +D` can hang on systems with many simulator daemons. Include associated native applications and child processes, not just obvious Node/Python workers. Inspect cwd and mapped executables as well as ordinary file handles.

A timeout, truncation, or failed query is not evidence of zero use. Re-query an appropriate process set. Use fresh evidence before deletion; keep live writers running and skip their data. Do not stop an emulator, build, app, or Git operation solely to make cleanup possible.

For a broader per-user probe, a bounded `lsof -nP -u <uid> -Fpcfatn` can capture process, descriptor, access mode, file type and path. Capture the complete result privately and filter exact candidate roots before presenting matches; truncating displayed raw output must not become the only evidence. Include executable/cwd use and configured paths found in worker arguments.

Distinguish use from verified metadata readers. A system application catalog can map a localized `InfoPlist.strings` label or hold a read-only descriptor to the top-level installation directory without running the target app. Verify the actual reader executable, descriptor/access/type and exact path; confirm that no target executable, descendant data file, writer or matching worker is active. Record the narrow exception. Never treat all read-only handles, all `txt` mappings, or an unfamiliar process as harmless.

## Applications and complete uninstalls

- Identify the selected bundle ID, installed version/build, actual executable and all product-owned locations. Native application metadata and Spotlight last-use dates support review; missing dates are not evidence of non-use. Installation/update dates and filesystem atime can be misleading.
- Explain bundle size by Frameworks, Resources, helpers, embedded languages/SDKs, architecture slices and assets. Do not delete inner components, locale folders, architecture slices or Xcode's signed tools as casual cleanup: removing signed contents can invalidate the containing app. Use supported component management or a selected whole-app uninstall.
- For a full selected uninstall, inspect both user/system Application Support, caches, preferences, Containers/Group Containers, shared vendor folders, helpers and startup registrations. Map service labels to their executable paths. Inspect product-owned privileged helpers, driver/system-extension registrations or login items when present; absence of a GUI process alone does not establish a complete uninstall.
- Prefer the installed vendor uninstaller or native management path after confirming product identity and supported arguments. An uninstaller failure does not prove removal; log it, inspect the resulting state, and complete only documented, authorized leftovers. Do not stop active jobs to enable an uninstall.
- Remove only the selected product's services. Shared Microsoft updater components, another Logitech camera service, Blackmagic components for a retained tool, and similar sibling services need their own dependency review. A whole vendor directory is not an exact product target.
- Preserve unique mail/notebooks, project databases, LUTs, presets, licenses and account state unless their deletion is selected. Back up small settings/macros/configuration privately when useful. Native preference-domain removal can clear cached preference values before deleting exact leftover stubs; do not kill the global preferences daemon.
- Inspect permissions/ACLs/flags before a large removal. Even a user-owned cached `.app` can reject deletion. If deletion becomes partial, record what remains and stop that item for a permitted native/administrator path; do not repeatedly strip flags or permissions across the enclosing Library tree. Check remaining signed apps for damage when applicable.
- Verify the main app and selected helpers are absent, own startup services are not loaded, and retained sibling products/data still exist. Distinguish full uninstall, cache-only cleanup, and retained user data in the receipt.

## Package stores and runtime retirement

1. Inventory versions, architecture, current defaults, version-manager aliases, command links, global tools and project requirements. Include embedded app runtimes. The newest version is not necessarily the current one: an older Node executable can host live MCP workers or be the default.
2. Resolve dependents before removing a runtime. For Python, inspect registered and unregistered environments, `pyvenv.cfg`, executable symlinks, script shebangs, `.pth`/editable links, and native-library dependencies where needed. For Java, inspect user/system JDKs, `java_home` selection and project configuration; preserve Android Studio's embedded JBR when required. Use targeted metadata/config inspection and avoid exposing secrets.
3. Treat a cache as its own selection. Native Conda/uv/Bun/npm and other prune commands may leave marker files or active entries. Preserve global tool installations and package authentication. A registered-environment list is not exhaustive. Hardlinked installed files survive unlinking a cache name and keep the shared blocks allocated; symlinks and path references into the removed cache can break environments.
4. If a compatible retained interpreter can safely support an environment during an authorized runtime retirement, save its original configuration/links and package inventory before rebinding it. Confirm architecture and language/ABI compatibility, unchanged installed packages, representative native imports and removal of old absolute framework dependencies. Otherwise keep the runtime and report the dependency. Do not silently rebuild or discard the environment to satisfy cleanup.
5. Remove only the selected installation and its exact now-obsolete command/path registrations. Do not remove an entire version pool when a version must remain. Verify the default executable and retained dependent environments after removal; report reinstall requirements for intentionally removed tools.

## Administrator batches and reliable completion

Complete eligible user-level cleanup first. Before requesting required local administrator authentication, prepare the exact remaining path manifest, preflight checks and one reviewable batch. Validate ownership, path identity, bundle metadata, symlink destinations and active use before and inside the privileged job. Keep paths within the selected scope; do not widen the batch to an entire Applications/Library directory.

Use a permitted native authorization route. Do not request or store the administrator password in chat, weaken sudo/SIP/privacy settings, or work around a blocked UI surface. Distinguish authorization cancellation from denial; do not automatically repeat a canceled request without a new user request.

Record script/manifest identity, the actual privileged child's UID, start/completion events, per-target failures and a final remaining-path list. Keep launch diagnostics and results readable by the target user inside the private audit directory, including early/preflight failures. A successful authorization-helper return is not the cleanup result. Wait for the real child job, inspect its result and verify the filesystem/services before claiming completion. If a batch is deferred, report the exact pending items; after completion, retire any temporary launcher that still invites unnecessary authentication.

## Generated dependencies, builds, and caches

- Search projects and nested/managed worktrees for installed dependencies, Pods, virtual environments, `.next`, DerivedData, and build output. Names are leads: a directory called `build`, `dist`, or `dotnet` can contain actual source.
- Within Git, check ignore status and `git ls-files -- <candidate>`; preserve tracked material. Require real project/build markers and reconstruction inputs. Keep pinned package/Pod lockfiles and workspace files. Save Python environment/package metadata before removing an idle environment when useful.
- Preserve active checkout dependencies and linked/custom package data. An inactive disposable installation can be removed without deleting its checkout, branch, worktree registration, or uncommitted source. State that dependencies must be reinstalled before reuse.
- When an obsolete worktree itself is selected, inspect tracked changes, untracked and ignored files, configuration and nested repositories before native Git removal. Preserve unique work privately and record its location. Do not mistake backing up settings for backing up all app state, and do not delete the worktree's branch/refs as an incidental cleanup step.
- Inspect scratch directories and app-managed build caches, including old `Claude/simulator-builds/*/DerivedData`. Validate the DerivedData metadata and source workspace; exclude anything a current build/runner uses.
- Closed old `.xcresult` bundles under `DerivedData/*/Logs/Test` can be disposable logs. Validate bundle metadata and absence of active test/build writers; preserve current results and evidence still needed by an investigation.
- Old `Library/Application Support/Caches/*-updater/pending` archives can be redundant downloads. Check package metadata, installed versions/age, and updater activity. Do not confuse them with installed applications or live profile databases.
- Use native package-manager cache cleanup where possible. For Conda, `clean --tarballs --index-cache --dry-run --json` distinguishes cached archives from installed packages. The CLI's `--packages` mode does not detect every symlink-backed environment; never force-remove its entire package directory.
- Preserve credentials, auth caches, active runtime distributions, container volumes, Docker disks, VM images, app databases, chat history, and offline content with unconfirmed disposability. A re-downloadable model cache differs from a custom trained model or active model installation.

## Android, iOS, and downloaded builds

Discover the configured SDK, AVD homes, and custom emulator directories; Android data may live under a project's output tree or `~/.local/share/`, not just `~/.android/avd`.

Read-only starting points include:

```bash
"${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}/platform-tools/adb" devices -l
xcrun simctl list devices --json
xcrun simctl list runtimes --json
```

- Map Android running emulator identities via adb's AVD-name query, process paths, configs, and open disk images. Preserve all profiles/data for active multi-profile investigations, even profiles not currently booted.
- Delete only verified obsolete/disposable devices. Prefer `avdmanager delete avd` for registered idle AVDs and `xcrun simctl delete <UUID>` for idle disposable iOS devices. Inspect custom/unregistered AVD configs before direct removal. Save small configs; do not imply that configs back up application data.
- Uninstall Android system images using `sdkmanager` only after checking retained AVD configurations and current SDK needs. Keep images required by active or retained development devices.
- Current booted devices and their runtimes remain. Dormant devices can still hold unique app state. Avoid broad simulator wipes and deleting physical device support required by the paired phone.
- For APK/IPA/AAB/APKS/XAPK/installers, combine dates, version metadata, current task/release use, and duplicates. A matching byte hash with a retained artifact is strong duplicate evidence. Keep the latest required reviewer/distribution formats; different formats or device splits are not automatically equivalent.

## Git temporary pack recurrence

1. Read `git count-objects -vH` in the affected repository. A `tmp_pack_*` name alone does not establish garbage. Preserve valid `.pack`, `.idx`, `.rev`, `.keep`, `.bitmap`, and related metadata.
2. Identify the writer and parent application. A `git add` can create large temporary packs while ingesting generated files; an unchanged mtime does not make a pack abandoned while its process/handle exists.
3. For an orphan candidate, take separate size/inode/mtime observations while doing independent work. Require stability, no live writer or open handle, and Git's garbage classification before removing the exact temporary file. Never cancel a live operation merely to satisfy those checks.
4. Record and check readable HEAD, retained pack metadata, and final garbage counts. `git prune-packed` can remove loose duplicates only after verifying the corresponding valid packs and accounting for concurrent activity. Avoid aggressive GC, repacks, pruning unique objects, or history rewrites as a casual cleanup tactic.
5. If large generated exports are being added repeatedly, inspect tracked versus untracked contents. Back up the repository's actual local exclude file, accounting for linked-worktree/common-dir layout. Add narrow patterns for confirmed generated payloads and test `git check-ignore` against both payloads and useful source/report paths. Existing tracked files are not untracked by exclusions.
6. State the effect and recovery path for local exclusions. Do not blanket-ignore all output, hide useful new source/reports, edit the Git index, disable background application features, or change global Git settings without appropriate scope. Verify subsequent eligible files/sizes and distinguish observed writer behavior from an unverified app-feature explanation.

To explain a large object database, inspect dominant pack/index sizes and use read-only Git object/path metadata to identify large retained blobs. Keep reachable history, reflog/recovery objects and unique unreachable content unless their removal has separate informed authorization. An old downloaded package embedded in a valid pack cannot be removed by unlinking that pack without losing its other objects. Separate a history-rewrite/archive proposal from routine cache or temporary-file cleanup.

## Optional transparent compression

Consider native filesystem compression only for old, inactive, compressible data that should retain its path. Preservation is preferable to deleting unique evidence; no savings is also a valid outcome.

`ditto --hfsCompression --noclone --rsrc --extattr --qtn --acl` is a native option on supported macOS filesystems. Check the installed tool's help. Pilot one file and verify a meaningful allocation reduction before considering a batch; some large or media-heavy files yield no benefit.

For any replacement: reject symlinks/shared hardlinks, recently modified files, open writers, and flagged files; preserve mode, owner, ACLs, extended attributes, and timestamps. Copy to a unique temporary sibling, hash original and copy, recheck original inode/size/mtime and content, then replace atomically only if stable. Verify the final hash and retain receipts. Always clean up only the temporary files created by this operation. Do not transform live databases, current logs/history, Git objects, or active VM/emulator disks.

Never report compression as deletion or add apparent compression savings to physical recovery without checking free space. Do not replace native file reads with archives or change original paths merely to increase a claimed total.
