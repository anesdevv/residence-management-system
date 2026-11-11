// web/src/lib/auth-flow.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import en from '../i18n/en.json';
import fr from '../i18n/fr.json';
import { evaluateEmailPairSubmission } from './email-form-client';
import { shouldGateStudentForEmail, checkUserNeedsContactEmail } from './email-gate';

const {
  mockSignUp,
  mockSignOut,
  mockSignInWithPassword,
  mockSetSession,
  mockRpc,
  mockFrom,
} = vi.hoisted(() => ({
  mockSignUp: vi.fn(),
  mockSignOut: vi.fn(),
  mockSignInWithPassword: vi.fn(),
  mockSetSession: vi.fn(),
  mockRpc: vi.fn(),
  mockFrom: vi.fn(),
}));

vi.mock('./supabase', () => ({
  createSupabaseServerClient: () => ({
    auth: {
      signUp: mockSignUp,
      signOut: mockSignOut,
      signInWithPassword: mockSignInWithPassword,
      setSession: mockSetSession,
    },
    rpc: mockRpc,
    from: mockFrom,
  }),
  cardIdToEmail: (cardId: string) => `${cardId.trim()}@students.residence.local`,
}));

import { POST as registerPost } from '../pages/api/register';
import { POST as loginPost } from '../pages/api/login';
import { POST as addEmailPost } from '../pages/api/account/add-email';
import { POST as profilePost } from '../pages/api/profile';

function makeFormContext(
  fields: Record<string, string>,
  opts: { user?: { id: string; email?: string } | null; locale?: 'en' | 'fr' } = {},
) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    fd.set(k, v);
  }
  const request = new Request('http://localhost:4321/api/test', {
    method: 'POST',
    body: fd,
  });
  return {
    request,
    cookies: { get: () => undefined, set: () => {}, delete: () => {} },
    locals: {
      locale: opts.locale ?? 'en',
      user: opts.user ?? null,
    },
    redirect: (location: string, status = 302) =>
      new Response(null, { status, headers: { Location: location } }),
  } as any;
}

describe('Register form & client email validation blocking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('blocks submission when emails differ or are missing', () => {
    const missing = evaluateEmailPairSubmission('', '');
    expect(missing.valid).toBe(false);
    expect(missing.message).toBe('Email address is required.');

    const differ = evaluateEmailPairSubmission('karim@univ-tlemcen.dz', 'other@univ-tlemcen.dz');
    expect(differ.valid).toBe(false);
    expect(differ.message).toBe('The emails do not match');

    const normalizedOk = evaluateEmailPairSubmission(
      '  Karim.Benali@Univ-Tlemcen.DZ  ',
      'karim.benali@univ-tlemcen.dz',
    );
    expect(normalizedOk.valid).toBe(true);
    expect(normalizedOk.normalizedEmail).toBe('karim.benali@univ-tlemcen.dz');
  });

  it('API /api/register blocks missing/mismatched emails and signs out session on success', async () => {
    const baseFields = {
      card_id: '20240001',
      first_name: 'Karim',
      last_name: 'Benali',
      birth_date: '2003-04-12',
      phone: '0555123456',
      email: 'karim@univ-tlemcen.dz',
      confirm_email: 'wrong@univ-tlemcen.dz',
      university: 'Université de Tlemcen',
      faculty: 'Sciences',
      study_level: 'L2',
      wilaya: 'Tlemcen',
      password: 'Password123!',
    };

    const mismatchRes = await registerPost(makeFormContext(baseFields));
    expect(mismatchRes.status).toBe(302);
    expect(mismatchRes.headers.get('Location')).toContain('The%20emails%20do%20not%20match');
    expect(mockSignUp).not.toHaveBeenCalled();

    // Valid registration
    mockRpc.mockResolvedValue({ data: { residence_name: 'RÉSIVO', residence_gender: 'male' }, error: null });
    mockSignUp.mockResolvedValue({
      data: {
        user: { id: 'u-1', identities: [{ id: 'id-1' }] },
        session: { access_token: 'tok', refresh_token: 'ref' },
      },
      error: null,
    });
    mockSignOut.mockResolvedValue({ error: null });

    const okRes = await registerPost(
      makeFormContext({
        ...baseFields,
        email: '  Karim@Univ-Tlemcen.DZ ',
        confirm_email: 'karim@univ-tlemcen.dz',
      }),
    );

    expect(mockSignUp).toHaveBeenCalledWith(
      expect.objectContaining({
        email: '20240001@students.residence.local',
        options: expect.objectContaining({
          data: expect.objectContaining({
            email: 'karim@univ-tlemcen.dz',
          }),
        }),
      }),
    );
    expect(mockSignOut).toHaveBeenCalled();
    expect(okRes.headers.get('Location')).toBe('/login?registered=1');
  });

  it('API /api/register maps email_in_use to friendly error', async () => {
    mockRpc.mockResolvedValue({ data: { residence_name: 'RÉSIVO', residence_gender: 'male' }, error: null });
    mockSignUp.mockResolvedValue({
      data: { user: null, session: null },
      error: { message: 'email_in_use: This email address is already registered to another student.' },
    });

    const res = await registerPost(
      makeFormContext({
        card_id: '20240001',
        first_name: 'Karim',
        last_name: 'Benali',
        birth_date: '2003-04-12',
        phone: '0555123456',
        email: 'karim@univ-tlemcen.dz',
        confirm_email: 'karim@univ-tlemcen.dz',
        university: 'Université de Tlemcen',
        faculty: 'Sciences',
        study_level: 'L2',
        wilaya: 'Tlemcen',
        password: 'Password123!',
      }),
    );
    expect(res.headers.get('Location')).toContain('already%20registered');
  });
});

describe('Add-email gate (legacy students without email only)', () => {
  it('gates ONLY students without an email and never gates staff or students with email', () => {
    expect(shouldGateStudentForEmail({ role: 'student', studentRow: { email: null } })).toBe(true);
    expect(shouldGateStudentForEmail({ role: 'student', studentRow: { email: '   ' } })).toBe(true);
    expect(shouldGateStudentForEmail({ role: 'student', studentRow: { email: 'karim@univ-tlemcen.dz' } })).toBe(false);
    expect(shouldGateStudentForEmail({ role: 'staff', studentRow: null })).toBe(false);
    expect(shouldGateStudentForEmail({ role: 'admin', studentRow: null })).toBe(false);
    expect(shouldGateStudentForEmail({ role: 'staff', studentRow: { email: null } })).toBe(false);
    expect(shouldGateStudentForEmail({ role: 'student', studentRow: null })).toBe(false);
  });

  it('checkUserNeedsContactEmail queries profiles and students and returns true only for null-email student', async () => {
    const makeMockSb = (role: string, studentRow: { email: string | null } | null) => ({
      from: (table: string) => ({
        select: () => ({
          eq: () => ({
            maybeSingle: async () =>
              table === 'profiles'
                ? { data: { role }, error: null }
                : { data: studentRow, error: null },
          }),
        }),
      }),
    });

    expect(await checkUserNeedsContactEmail(makeMockSb('student', { email: null }), 'u1')).toBe(true);
    expect(await checkUserNeedsContactEmail(makeMockSb('student', { email: 's@univ.dz' }), 'u2')).toBe(false);
    expect(await checkUserNeedsContactEmail(makeMockSb('staff', null), 'u3')).toBe(false);
    expect(await checkUserNeedsContactEmail(makeMockSb('admin', null), 'u4')).toBe(false);
  });

  it('POST /api/login resolves Card ID via student-login, rejects email sign-in, and routes legacy null-email students to /account/add-email', async () => {
    const emailLoginRes = await loginPost(
      makeFormContext({ card_id: 'student@univ-tlemcen.dz', password: 'Password123!' }),
    );
    expect(emailLoginRes.headers.get('Location')).toContain('/login?error=');

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          session: { access_token: 'tok', refresh_token: 'ref' },
          user: { id: 'u-legacy' },
          needs_email: true,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    mockSetSession.mockResolvedValue({ error: null });

    const legacyRes = await loginPost(
      makeFormContext({ card_id: '202138099888', password: 'Password123!' }),
    );
    expect(legacyRes.headers.get('Location')).toBe('/account/add-email');

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          session: { access_token: 'tok2', refresh_token: 'ref2' },
          user: { id: 'u-ok' },
          needs_email: false,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const okRes = await loginPost(
      makeFormContext({ card_id: '202338012345', password: 'Password123!' }),
    );
    expect(okRes.headers.get('Location')).toBe('/dashboard');
    fetchSpy.mockRestore();
  });

  it('POST /api/account/add-email saves via update_my_contact and redirects to /dashboard', async () => {
    mockFrom.mockReturnValue({
      select: () => ({
        eq: () => ({
          maybeSingle: async () => ({ data: { phone: '0555334455' }, error: null }),
        }),
      }),
    });
    mockRpc.mockResolvedValue({ data: { id: 'u-legacy' }, error: null });

    const res = await addEmailPost(
      makeFormContext(
        { email: '  Tariq@Univ-Tlemcen.DZ ', confirm_email: 'tariq@univ-tlemcen.dz' },
        { user: { id: 'u-legacy' } },
      ),
    );
    expect(mockRpc).toHaveBeenCalledWith('update_my_contact', {
      p_phone: '0555334455',
      p_email: 'tariq@univ-tlemcen.dz',
    });
    expect(res.headers.get('Location')).toBe('/dashboard');
  });
});

describe('Profile contact update', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('POST /api/profile updates phone and contact email via update_my_contact', async () => {
    mockRpc.mockResolvedValue({ data: { id: 'u-1' }, error: null });

    const res = await profilePost(
      makeFormContext(
        {
          phone: '0555112233',
          email: '  Karim.New@Univ-Tlemcen.DZ ',
          confirm_email: 'karim.new@univ-tlemcen.dz',
        },
        { user: { id: 'u-1' } },
      ),
    );

    expect(mockRpc).toHaveBeenCalledWith('update_my_contact', {
      p_phone: '0555112233',
      p_email: 'karim.new@univ-tlemcen.dz',
    });
    expect(res.headers.get('Location')).toBe('/dashboard/profile?updated=1');
  });

  it('POST /api/profile rejects mismatched confirmation email and maps email_in_use', async () => {
    const mismatch = await profilePost(
      makeFormContext(
        {
          phone: '0555112233',
          email: 'a@univ-tlemcen.dz',
          confirm_email: 'b@univ-tlemcen.dz',
        },
        { user: { id: 'u-1' } },
      ),
    );
    expect(mismatch.headers.get('Location')).toContain('The%20emails%20do%20not%20match');
    expect(mockRpc).not.toHaveBeenCalled();

    mockRpc.mockResolvedValue({
      data: null,
      error: { message: 'email_in_use: This email address is already in use by another student.' },
    });
    const dup = await profilePost(
      makeFormContext(
        {
          phone: '0555112233',
          email: 'taken@univ-tlemcen.dz',
          confirm_email: 'taken@univ-tlemcen.dz',
        },
        { user: { id: 'u-1' } },
      ),
    );
    expect(dup.headers.get('Location')).toContain('already%20registered');
  });
});

describe('Simple-email source contracts, deleted flows & i18n parity', () => {
  function flattenKeys(obj: Record<string, unknown>, prefix = ''): Record<string, string> {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(obj)) {
      const full = prefix ? `${prefix}.${k}` : k;
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        Object.assign(out, flattenKeys(v as Record<string, unknown>, full));
      } else {
        out[full] = String(v);
      }
    }
    return out;
  }

  it('keeps 100% key and placeholder parity between web EN and FR catalogs', () => {
    const enFlat = flattenKeys(en);
    const frFlat = flattenKeys(fr);
    expect(Object.keys(enFlat).filter((k) => !(k in frFlat))).toEqual([]);
    expect(Object.keys(frFlat).filter((k) => !(k in enFlat))).toEqual([]);

    const paramRe = /\{([a-zA-Z0-9_]+)\}/g;
    for (const key of Object.keys(enFlat)) {
      const enParams = [...enFlat[key].matchAll(paramRe)].map((m) => m[1]).sort();
      const frParams = [...frFlat[key].matchAll(paramRe)].map((m) => m[1]).sort();
      expect(frParams, `Placeholder mismatch on key ${key}`).toEqual(enParams);
    }
  });

  it('removes all deleted email verification and recovery pages, components, and auth API calls from web/src', () => {
    const srcDir = path.resolve(import.meta.dirname, '..');
    const deletedPaths = [
      'pages/' + 'verify-email.astro',
      'pages/fr/' + 'verify-email.astro',
      'pages/auth/confirm.ts',
      'pages/' + 'forgot-password.astro',
      'pages/fr/' + 'forgot-password.astro',
      'pages/' + 'reset-password.astro',
      'pages/fr/' + 'reset-password.astro',
      'pages/api/auth/' + 'verify-code.ts',
      'pages/api/auth/' + 'resend-code.ts',
      'pages/api/auth/' + 'request-password-reset.ts',
      'pages/api/auth/' + 'request-login-link.ts',
      'pages/api/auth/' + 'reset-password.ts',
      'components/OtpInput.astro',
      'components/ResendButton.astro',
      'lib/' + 'resend-cooldown.ts',
    ];
    for (const rel of deletedPaths) {
      expect(fs.existsSync(path.join(srcDir, rel)), `${rel} should be deleted`).toBe(false);
    }

    const forbiddenPatterns = [
      new RegExp(['signIn', 'WithOtp'].join('')),
      new RegExp(['resetPassword', 'ForEmail'].join('')),
      new RegExp(['verify', 'Otp'].join('')),
      new RegExp(['\\bresend', '\\s*\\('].join('')),
      new RegExp(['magic', 'link'].join(''), 'i'),
    ];

    function walk(dir: string): string[] {
      const files: string[] = [];
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          files.push(...walk(full));
        } else if (!entry.name.endsWith('.test.ts')) {
          files.push(full);
        }
      }
      return files;
    }

    for (const file of walk(srcDir)) {
      const content = fs.readFileSync(file, 'utf8');
      for (const re of forbiddenPatterns) {
        expect(re.test(content), `${file} matched forbidden pattern ${re}`).toBe(false);
      }
    }

    // Profile must never show "Verified" next to email
    const profileAstro = fs.readFileSync(path.join(srcDir, 'pages/dashboard/profile.astro'), 'utf8');
    expect(profileAstro).not.toContain('verified_email_pill');
    expect(profileAstro).not.toContain('readonly');

    // Register must allow paste, set autocomplete=email & inputmode=email, and have confirm_email
    const registerAstro = fs.readFileSync(path.join(srcDir, 'pages/register.astro'), 'utf8');
    expect(registerAstro).toContain('name="confirm_email"');
    expect(registerAstro).toContain('autocomplete="email"');
    expect(registerAstro).toContain('inputmode="email"');
    expect(registerAstro).not.toContain('onpaste');
  });
});
