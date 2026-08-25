import { ReactNode } from 'react'
import './TabContent.css'

interface TabContentProps {
  tabs: Array<{
    id: string
    content: ReactNode
  }>
  activeTabId: string
}

/**
 * TabContent renders all tabs but only displays the active one.
 * This is critical: tabs stay mounted to preserve state (especially for WebSocket-backed terminal).
 */
export function TabContent({ tabs, activeTabId }: TabContentProps) {
  return (
    <div className="tab-content-container">
      {tabs.map(tab => (
        <div
          key={tab.id}
          className="tab-content"
          style={{ display: tab.id === activeTabId ? 'block' : 'none' }}
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
}
