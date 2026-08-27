import { useState, useEffect } from 'react'
import './App.css'
import { LayoutShell } from './components/LayoutShell'
import { TabBar } from './components/TabBar'
import { TabContent } from './components/TabContent'
import { NarrativePane } from './components/NarrativePane'
import { TerminalPane } from './components/TerminalPane'
import { IframePane } from './components/IframePane'
import { StepNav } from './components/StepNav'
import type { Tab } from './types'

interface Session {
  session_id: string
  exhibit_id: string
  current_step: string
}

interface Pane {
  type: 'terminal' | 'iframe'
  label: string
  path?: string
}

interface StepData {
  step: {
    id: string
    panes: Pane[]
    next: string | null
  }
  narrative_content: string
  has_next: boolean
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [stepData, setStepData] = useState<StepData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTabId, setActiveTabId] = useState('')
  const [stepHistory, setStepHistory] = useState<string[]>([])

  const startSession = async (exhibitId: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/sessions?exhibit_id=${exhibitId}`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`)
      }

      const data = await response.json()
      setSession(data)
      setStepHistory([])
      console.log('Session created:', data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      console.error('Error creating session:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadCurrentStep = async (sessionId: string) => {
    try {
      const response = await fetch(`/api/sessions/${sessionId}/step`)
      if (!response.ok) throw new Error('Failed to load step')

      const data: StepData = await response.json()
      setStepData(data)

      // Set active tab to first pane
      if (data.step.panes.length > 0) {
        setActiveTabId(data.step.panes[0].type + '-0')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load step')
      console.error('Error loading step:', err)
    }
  }

  const goToNextStep = async () => {
    if (!session) return

    try {
      // Save current step to history
      setStepHistory(prev => [...prev, session.current_step])

      const response = await fetch(`/api/sessions/${session.session_id}/next`, {
        method: 'POST',
      })

      if (!response.ok) throw new Error('Failed to go to next step')

      await loadCurrentStep(session.session_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to advance')
      console.error('Error going to next step:', err)
    }
  }

  const goToPreviousStep = async () => {
    if (!session || stepHistory.length === 0) return

    try {
      const previousStepId = stepHistory[stepHistory.length - 1]
      setStepHistory(prev => prev.slice(0, -1))

      const response = await fetch(`/api/sessions/${session.session_id}/step`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_id: previousStepId })
      })

      if (!response.ok) throw new Error('Failed to go back')

      await loadCurrentStep(session.session_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to go back')
      console.error('Error going to previous step:', err)
    }
  }

  // Load step data when session changes
  useEffect(() => {
    if (session) {
      loadCurrentStep(session.session_id)
    }
  }, [session])

  // Show layout if session and step data exist
  if (session && stepData) {
    // Build tabs from step panes
    const tabs: Tab[] = stepData.step.panes.map((pane, idx) => ({
      id: pane.type + '-' + idx,
      label: pane.label,
      type: pane.type,
    }))

    // Build tab contents
    const tabContents = stepData.step.panes.map((pane, idx) => {
      const id = pane.type + '-' + idx

      if (pane.type === 'terminal') {
        return { id, content: <TerminalPane sessionId={session.session_id} /> }
      } else {
        const url = pane.path || 'http://localhost:9000'
        return { id, content: <IframePane url={url} label={pane.label} /> }
      }
    })

    return (
      <LayoutShell
        narrative={
          <NarrativePane
            content={stepData.narrative_content}
            onSwitchToTerminal={() => {
              // Switch to first terminal tab if exists
              const terminalTab = tabs.find(t => t.type === 'terminal')
              if (terminalTab) {
                setActiveTabId(terminalTab.id)
              }
            }}
          />
        }
        tabbedContent={
          <>
            {tabs.length > 0 && (
              <>
                <TabBar tabs={tabs} activeTabId={activeTabId} onTabChange={setActiveTabId} />
                <TabContent tabs={tabContents} activeTabId={activeTabId} />
              </>
            )}
            <StepNav
              canGoBack={stepHistory.length > 0}
              canGoNext={stepData.has_next}
              onPrevious={goToPreviousStep}
              onNext={goToNextStep}
            />
          </>
        }
      />
    )
  }

  // Loading step data
  if (session && !stepData) {
    return (
      <div className="app">
        <header>
          <h1>Eumatheia</h1>
        </header>
        <main style={{ textAlign: 'center', padding: '4rem' }}>
          <p className="status">Loading step...</p>
        </main>
      </div>
    )
  }

  // Initial screen: session selection
  return (
    <div className="app">
      <header>
        <h1>Eumatheia React Frontend</h1>
        <p>Interactive Software Engineering Learning Platform</p>
      </header>

      <main>
        <div className="session-controls">
          <h2>Start a Session</h2>

          <div className="button-group">
            <button
              onClick={() => startSession('demo')}
              disabled={loading}
            >
              Start Demo
            </button>

            <button
              onClick={() => startSession('fastapi-crud')}
              disabled={loading}
            >
              Start FastAPI Tutorial
            </button>

            <button
              onClick={() => startSession('docker-demo')}
              disabled={loading}
            >
              Start Docker Demo (Ancillary Files)
            </button>
          </div>

          {loading && <p className="status">Creating session...</p>}
          {error && <p className="error">Error: {error}</p>}
        </div>

        <div className="next-steps">
          <h2>Development Status - Steps 3 & 4 Complete!</h2>
          <ul>
            <li>✅ Vite + React + TypeScript scaffolded</li>
            <li>✅ LayoutShell component with side/top toggle</li>
            <li>✅ TabBar/TabContent with always-mounted pattern</li>
            <li>✅ NarrativePane with markdown parsing & copy buttons</li>
            <li>✅ StepNav with back/forward navigation</li>
            <li>✅ Real API integration with step data</li>
            <li>✅ Dynamic tabs from exhibit configuration</li>
            <li>🔨 Next: Swap orchestrator to serve React dist</li>
            <li>🔨 Next: Add Docker multi-stage build</li>
          </ul>
        </div>
      </main>
    </div>
  )
}

export default App
