import './StepNav.css'

interface StepNavProps {
  canGoBack: boolean
  canGoNext: boolean
  onPrevious: () => void
  onNext: () => void
}

/**
 * StepNav provides back/forward navigation between tutorial steps.
 */
export function StepNav({ canGoBack, canGoNext, onPrevious, onNext }: StepNavProps) {
  return (
    <div className="step-nav">
      <button
        className="nav-button prev"
        onClick={onPrevious}
        disabled={!canGoBack}
        title="Previous step"
      >
        ← Previous
      </button>

      <button
        className="nav-button next"
        onClick={onNext}
        disabled={!canGoNext}
        title="Next step"
      >
        Next →
      </button>
    </div>
  )
}
