import { RouterProvider } from 'react-router'
import { router } from './router'
import { useAuth } from './hooks/useAuth'
import { AuthContext } from './contexts/AuthContext'

export function Root() {
  const auth = useAuth('http://127.0.0.1:8000')

  return (
    <AuthContext.Provider value={auth}>
      <RouterProvider router={router} />
    </AuthContext.Provider>
  )
}
