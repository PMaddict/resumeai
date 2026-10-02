import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { History } from './pages/History'
import { JDTailoring } from './pages/JDTailoring'
import { Profile } from './pages/Profile'
import { ResumeVault } from './pages/ResumeVault'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/vault" element={<ResumeVault />} />
        <Route path="/tailor" element={<JDTailoring />} />
        <Route path="/history" element={<History />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}

export default App
