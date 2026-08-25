import './TerminalPane.css'

interface TerminalPaneProps {
  sessionId: string
}

/**
 * TerminalPane renders an iframe to the gotty terminal.
 * The iframe MUST stay mounted to preserve the WebSocket connection and shell session.
 */
export function TerminalPane({ sessionId }: TerminalPaneProps) {
  // For now, use the shared terminal on port 7681
  // Later: route to per-session terminal via session_id
  const terminalUrl = 'http://localhost:7681'

  return (
    <div className="terminal-pane">
      <iframe
        src={terminalUrl}
        title={`Terminal - ${sessionId}`}
        className="terminal-iframe"
      />
    </div>
  )
}
