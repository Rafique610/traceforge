import { Dashboard } from './dashboard/Dashboard'
import { FactorialView } from './evaluation/FactorialView'
import { RunDetail } from './evaluation/RunDetail'
import { RunList } from './evaluation/RunList'
import { IncidentDetail } from './incidents/IncidentDetail'
import { IncidentList } from './incidents/IncidentList'
import { NewIncidentPage } from './incidents/NewIncident'
import { Shell } from './layout/Shell'
import { ErrorBoundary, NotFound } from './shared/ErrorBoundary'
import { useRoute } from './shared/router'

export default function App() {
  const route = useRoute()
  const key = route.name + ('id' in route ? route.id : '') + ('runs' in route ? route.runs.join(',') : '')
  return (
    <Shell>
      <ErrorBoundary resetKey={key}>
        {route.name === 'dashboard' && <Dashboard />}
        {route.name === 'list' && <IncidentList />}
        {route.name === 'new' && <NewIncidentPage />}
        {route.name === 'detail' && <IncidentDetail key={route.id} id={route.id} />}
        {route.name === 'eval-list' && <RunList />}
        {route.name === 'eval-detail' && <RunDetail key={route.id} id={route.id} />}
        {route.name === 'eval-compare' && <FactorialView runIds={route.runs} />}
        {route.name === 'not-found' && <NotFound />}
      </ErrorBoundary>
    </Shell>
  )
}
