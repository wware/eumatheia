import './TabBar.css'
import type { Tab } from '../types'

interface TabBarProps {
  tabs: Tab[]
  activeTabId: string
  onTabChange: (tabId: string) => void
}

export function TabBar({ tabs, activeTabId, onTabChange }: TabBarProps) {
  if (tabs.length === 0) {
    return null
  }

  return (
    <div className="tab-bar">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab ${tab.id === activeTabId ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.type === 'terminal' ? '⌨️' : '🖥️'} {tab.label}
        </button>
      ))}
    </div>
  )
}
