import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

export type ModelKey = 'fair' | 'base'

interface ModelContextValue {
  model: ModelKey
  setModel: (m: ModelKey) => void
}

const ModelContext = createContext<ModelContextValue>({
  model: 'fair',
  setModel: () => {},
})

const STORAGE_KEY = 'filtrant_active_model'

export function ModelProvider({ children }: { children: ReactNode }) {
  const [model, setModelState] = useState<ModelKey>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === 'base' ? 'base' : 'fair'
  })

  const setModel = (m: ModelKey) => {
    localStorage.setItem(STORAGE_KEY, m)
    setModelState(m)
  }

  return (
    <ModelContext.Provider value={{ model, setModel }}>
      {children}
    </ModelContext.Provider>
  )
}

export function useModel() {
  return useContext(ModelContext)
}

/** Pick the right field from a candidate row based on the active model. */
export function useModelFields(c: {
  recommendation: string
  confidence: number | null
  recommendation_base: string | null
  confidence_base: number | null
}) {
  const { model } = useModel()
  return {
    recommendation: (model === 'base' ? c.recommendation_base : c.recommendation) ?? c.recommendation,
    confidence: model === 'base' ? c.confidence_base : c.confidence,
  }
}
