import { EmptyState, PanelNotice, Pill, SectionHeader } from '../primitives'

export function WorkspaceStatus({
  dataSource,
  notices,
}: {
  dataSource: 'live' | 'demo'
  notices: string[]
}) {
  const uniqueNotices = Array.from(new Set(notices.filter(Boolean)))
  const statusTone = dataSource === 'live' ? 'success' : 'warning'
  const statusLabel = dataSource === 'live' ? 'Backend connected' : 'Demo fallback active'
  const description =
    dataSource === 'live'
      ? 'The frontend is currently reading live backend contracts for the connected surfaces below.'
      : 'One or more contract surfaces are using demo fallback right now. Keep the UI honest about that mode instead of masking it.'

  return (
    <section className="glass-panel flex flex-col gap-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <SectionHeader
          eyebrow="Workspace status"
          title="Connection and fallback posture"
          description={description}
        />
        <Pill label={statusLabel} tone={statusTone} />
      </div>
      {uniqueNotices.length === 0 ? (
        <EmptyState
          title="No active contract notices"
          description="The current connected surfaces are not reporting a refresh or fallback warning."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {uniqueNotices.map((notice) => (
            <PanelNotice key={notice} message={notice} tone={dataSource === 'live' ? 'muted' : 'error'} />
          ))}
        </div>
      )}
    </section>
  )
}
