export function StateBadge({ state }: { state: string }) {
  return (
    <span className={`state state-${state.toLowerCase()}`} data-testid="state-badge">
      {state.replace(/_/g, ' ')}
    </span>
  )
}
