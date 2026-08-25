import { ReactNode, useState } from 'react'
import './LayoutShell.css'

interface LayoutShellProps {
  narrative: ReactNode
  tabbedContent: ReactNode
}

type NarrativePosition = 'side' | 'top'

export function LayoutShell({ narrative, tabbedContent }: LayoutShellProps) {
  const [narrativePosition, setNarrativePosition] = useState<NarrativePosition>('side')

  const togglePosition = () => {
    setNarrativePosition(prev => prev === 'side' ? 'top' : 'side')
  }

  return (
    <div className="layout-shell">
      <header className="layout-header">
        <h1>Eumatheia</h1>
        <button
          className="position-toggle"
          onClick={togglePosition}
          title={`Switch to ${narrativePosition === 'side' ? 'top' : 'side'} layout`}
        >
          {narrativePosition === 'side' ? '⬆️ Top' : '⬅️ Side'}
        </button>
      </header>

      <div className={`layout-content layout-${narrativePosition}`}>
        <div className="narrative-pane">
          {narrative}
        </div>
        <div className="tabbed-content">
          {tabbedContent}
        </div>
      </div>
    </div>
  )
}
