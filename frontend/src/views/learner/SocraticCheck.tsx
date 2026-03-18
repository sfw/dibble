import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router'
import { ChevronLeft, MessageCircle, Send } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useSocraticWorkspace } from '../../hooks/useSocraticWorkspace'
import type { DataSource } from '../../app/workspace'
import type { GeneratedBlock } from '../../types'

const confidenceLevels = [
  { value: '0.25', label: 'Not sure', emoji: '🤔' },
  { value: '0.50', label: 'Somewhat', emoji: '😐' },
  { value: '0.75', label: 'Pretty sure', emoji: '🙂' },
  { value: '1.00', label: 'Very sure', emoji: '😊' },
]

export function SocraticCheck() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const { config, workspace } = useOutletContext<LearnerContext>()
  const navigate = useNavigate()

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const socratic = useSocraticWorkspace({
    config,
    learnerId: workspace.student_id,
    workspace,
    onDataSourceChange: handleDataSourceChange,
  })

  const [response, setResponse] = useState('')
  const [confidence, setConfidence] = useState('0.75')

  const session = socratic.session
  const latestTurn = session.turns[session.turns.length - 1]
  const conversationHistory = session.conversation_history ?? []
  const hints = socratic.response?.generated_blocks ?? []

  function handleSubmit() {
    socratic.setForm((current) => ({
      ...current,
      session_id: sessionId ?? session.session_id,
      learner_response: response,
      learner_confidence: confidence,
    }))
    void socratic.handleRun()
    setResponse('')
  }

  return (
    <PageContainer size="narrow" className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate('/learn')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to home
      </button>

      {/* Header */}
      <header className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
          <MessageCircle className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Understanding check
          </p>
          <h1 className="text-xl font-semibold">
            Let's see what you know
          </h1>
        </div>
      </header>

      {/* Conversation thread */}
      <div className="flex flex-col gap-3">
        {conversationHistory.map((entry, index) => (
          <ChatBubble
            key={index}
            role={entry.role}
            text={entry.text}
          />
        ))}

        {/* Latest prompt if not already in history */}
        {latestTurn && !conversationHistory.length && (
          <ChatBubble role="assistant" text={latestTurn.prompt} />
        )}
      </div>

      {/* Support panel (scaffolded hints) */}
      {hints.length > 0 && (
        <details className="rounded-xl border bg-slate-50 p-4">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
            Need a hint?
          </summary>
          <div className="mt-3 flex flex-col gap-2">
            {hints.map((block, index) => (
              <HintCard key={index} block={block} />
            ))}
          </div>
        </details>
      )}

      {/* Confidence picker */}
      <div>
        <p className="mb-2 text-sm font-medium">How confident are you?</p>
        <div className="grid grid-cols-4 gap-2">
          {confidenceLevels.map((level) => (
            <button
              key={level.value}
              onClick={() => setConfidence(level.value)}
              className={`flex flex-col items-center gap-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                confidence === level.value
                  ? 'border-violet-300 bg-violet-50 text-violet-700'
                  : 'border-transparent bg-slate-50 text-muted-foreground hover:bg-slate-100'
              }`}
            >
              <span className="text-lg">{level.emoji}</span>
              <span className="text-xs">{level.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Response composer */}
      <div className="flex flex-col gap-3">
        <Textarea
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          placeholder="Type your answer..."
          className="min-h-[100px] resize-none"
        />
        <Button
          onClick={handleSubmit}
          disabled={socratic.loading || !response.trim()}
          className="w-full"
          size="lg"
        >
          <Send className="mr-2 h-4 w-4" />
          {socratic.loading ? 'Checking...' : 'Submit your answer'}
        </Button>
      </div>

      {socratic.error && (
        <p className="text-sm text-red-600">{socratic.error}</p>
      )}
    </PageContainer>
  )
}

function ChatBubble({ role, text }: { role: string; text: string }) {
  const isLearner = role === 'learner' || role === 'user'
  return (
    <div className={`flex ${isLearner ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isLearner
            ? 'bg-blue-600 text-white'
            : 'bg-white border shadow-sm'
        }`}
      >
        {text}
      </div>
    </div>
  )
}

function HintCard({ block }: { block: GeneratedBlock }) {
  return (
    <div className="rounded-lg bg-white p-3 text-sm">
      {block.title && <p className="mb-1 font-medium">{block.title}</p>}
      <p className="text-muted-foreground">{block.body}</p>
    </div>
  )
}
