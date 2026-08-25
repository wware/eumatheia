import './IframePane.css'

interface IframePaneProps {
  url: string
  label: string
}

/**
 * IframePane renders an external application in an iframe.
 * The iframe stays mounted to preserve application state.
 */
export function IframePane({ url, label }: IframePaneProps) {
  return (
    <div className="iframe-pane">
      <iframe
        src={url}
        title={label}
        className="app-iframe"
      />
    </div>
  )
}
