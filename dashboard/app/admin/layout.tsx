import { createSupabaseServerClient } from '@/lib/supabase-server'
import { signOut } from './login/actions'

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createSupabaseServerClient()
  const { data: { user } } = await supabase.auth.getUser()

  return (
    <>
      {user && (
        <div className="bg-zinc-900 border-b border-zinc-800 px-4 py-2 flex items-center justify-between text-sm">
          <span className="text-zinc-500">{user.email}</span>
          <form action={signOut}>
            <button
              type="submit"
              className="text-zinc-400 hover:text-white transition-colors"
            >
              Sign out
            </button>
          </form>
        </div>
      )}
      {children}
    </>
  )
}
