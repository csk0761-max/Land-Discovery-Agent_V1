import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase credentials missing. Check your .env file.')
}

export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey)
  : {
      auth: {
        async getSession() {
          return { data: { session: null } }
        },
        async signInWithPassword() {
          return { error: new Error('Supabase is not configured.') }
        },
        async signUp() {
          return { error: new Error('Supabase is not configured.') }
        },
        async signOut() {
          return { error: new Error('Supabase is not configured.') }
        },
        onAuthStateChange() {
          return { data: { subscription: { unsubscribe() {} } } }
        },
      },
    }
