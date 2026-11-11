// web/src/lib/email-form-client.ts
import { validateContactEmailPair, normalizeEmail } from './validation';
import type { SupportedLocale } from './i18n';

export interface EmailFormBindingOptions {
  form: HTMLFormElement;
  emailInput: HTMLInputElement;
  confirmInput: HTMLInputElement;
  errorEl?: HTMLElement | null;
  locale?: SupportedLocale;
}

/**
 * Pure validation helper usable both in unit tests (without DOM) and in the browser.
 * Normalizes emails (trim + lowercase) and enforces format, max length (254), and matching.
 */
export function evaluateEmailPairSubmission(
  emailRaw: string,
  confirmRaw: string,
  locale: SupportedLocale = 'en',
): { valid: boolean; normalizedEmail: string; normalizedConfirm: string; message: string } {
  const normalizedEmail = normalizeEmail(emailRaw ?? '');
  const normalizedConfirm = normalizeEmail(confirmRaw ?? '');
  const res = validateContactEmailPair(normalizedEmail, normalizedConfirm, locale);
  if (!res.ok) {
    return {
      valid: false,
      normalizedEmail,
      normalizedConfirm,
      message: res.message,
    };
  }
  return {
    valid: true,
    normalizedEmail: res.email,
    normalizedConfirm,
    message: '',
  };
}

/**
 * Wires live email + confirm-email validation to a form without blocking pasting.
 * Prevents submission when email is missing, invalid, or does not match confirm email.
 */
export function attachEmailConfirmValidation({
  form,
  emailInput,
  confirmInput,
  errorEl,
  locale = 'en',
}: EmailFormBindingOptions) {
  function syncValidity(showConfirmError: boolean): boolean {
    const check = evaluateEmailPairSubmission(emailInput.value, confirmInput.value, locale);

    emailInput.setCustomValidity('');
    confirmInput.setCustomValidity('');

    if (!check.valid) {
      const hasConfirm = Boolean(check.normalizedConfirm);
      const pairOnlyMismatch =
        Boolean(check.normalizedEmail) &&
        validateContactEmailPair(check.normalizedEmail, undefined, locale).ok &&
        check.normalizedEmail !== check.normalizedConfirm;

      if (pairOnlyMismatch) {
        if (hasConfirm || showConfirmError) {
          confirmInput.setCustomValidity(check.message);
        }
      } else if (showConfirmError) {
        if (!check.normalizedEmail || !validateContactEmailPair(check.normalizedEmail, undefined, locale).ok) {
          emailInput.setCustomValidity(check.message);
        } else {
          confirmInput.setCustomValidity(check.message);
        }
      }

      if (errorEl) {
        if (showConfirmError || (pairOnlyMismatch && hasConfirm)) {
          errorEl.textContent = check.message;
          errorEl.classList.remove('hidden');
        } else {
          errorEl.textContent = '';
          errorEl.classList.add('hidden');
        }
      }
      return false;
    }

    if (errorEl) {
      errorEl.textContent = '';
      errorEl.classList.add('hidden');
    }
    return true;
  }

  emailInput.addEventListener('input', () => syncValidity(false));
  confirmInput.addEventListener('input', () => syncValidity(false));

  form.addEventListener('submit', (e) => {
    emailInput.value = normalizeEmail(emailInput.value);
    confirmInput.value = normalizeEmail(confirmInput.value);
    const valid = syncValidity(true);
    if (!valid) {
      e.preventDefault();
      delete form.dataset.submitting;
      confirmInput.reportValidity();
      if (!emailInput.validity.valid) {
        emailInput.reportValidity();
      }
    }
  });
}
