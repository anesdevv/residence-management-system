/// <reference types="astro/client" />
import type { User } from '@supabase/supabase-js';
import type { SupportedLocale } from './lib/i18n';

declare global {
  namespace App {
    interface Locals {
      user: User | null;
      locale: SupportedLocale;
    }
  }
}
