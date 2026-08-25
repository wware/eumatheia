import { useEffect, useRef } from 'react'
import { marked } from 'marked'
import './NarrativePane.css'

interface NarrativePaneProps {
  content: string
  onSwitchToTerminal?: () => void
}

/**
 * NarrativePane renders markdown content for the current step.
 * Includes "Copy" buttons on code blocks for easy copying to clipboard.
 */
export function NarrativePane({ content, onSwitchToTerminal }: NarrativePaneProps) {
  const narrativeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!narrativeRef.current) return

    // Parse markdown
    const html = marked.parse(content) as string
    narrativeRef.current.innerHTML = html

    // Add copy buttons to code blocks
    const codeBlocks = narrativeRef.current.querySelectorAll('pre code')
    codeBlocks.forEach((codeEl) => {
      const pre = codeEl.parentElement
      if (!pre) return

      const code = codeEl.textContent || ''

      // Create copy button
      const copyBtn = document.createElement('button')
      copyBtn.className = 'copy-code-btn'
      copyBtn.textContent = 'Copy'
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(code)
          copyBtn.textContent = 'Copied!'
          setTimeout(() => {
            copyBtn.textContent = 'Copy'
          }, 2000)

          // Optionally switch to terminal tab after copying
          if (onSwitchToTerminal) {
            setTimeout(() => {
              onSwitchToTerminal()
            }, 300)
          }
        } catch (err) {
          console.error('Failed to copy:', err)
          copyBtn.textContent = 'Failed'
          setTimeout(() => {
            copyBtn.textContent = 'Copy'
          }, 2000)
        }
      }

      pre.style.position = 'relative'
      pre.appendChild(copyBtn)
    })
  }, [content, onSwitchToTerminal])

  return (
    <div className="narrative-pane-content">
      <div className="narrative-text" ref={narrativeRef}></div>
    </div>
  )
}
