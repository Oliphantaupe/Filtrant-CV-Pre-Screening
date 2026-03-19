import { motion } from 'motion/react'
import { useEffect, useRef, useState, useMemo } from 'react'

type BlurTextProps = {
  text?: string
  delay?: number
  className?: string
  animateBy?: 'words' | 'letters'
  direction?: 'top' | 'bottom'
  threshold?: number
  onAnimationComplete?: () => void
  stepDuration?: number
}

export default function BlurText({
  text = '',
  delay = 80,
  className = '',
  animateBy = 'words',
  direction = 'bottom',
  threshold = 0.1,
  onAnimationComplete,
  stepDuration = 0.3,
}: BlurTextProps) {
  const elements = animateBy === 'words' ? text.split(' ') : text.split('')
  const [inView, setInView] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setInView(true); observer.disconnect() } },
      { threshold }
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [threshold])

  const from = useMemo(
    () => (direction === 'top'
      ? { filter: 'blur(8px)', opacity: 0, y: -20 }
      : { filter: 'blur(8px)', opacity: 0, y: 20 }),
    [direction]
  )

  const toSteps = useMemo(
    () => [
      { filter: 'blur(4px)', opacity: 0.5, y: direction === 'top' ? 4 : -4 },
      { filter: 'blur(0px)', opacity: 1, y: 0 },
    ],
    [direction]
  )

  const totalDuration = stepDuration * toSteps.length
  const times = [0, ...toSteps.map((_, i) => (i + 1) / toSteps.length)]

  const keyframes = {
    filter: [from.filter, ...toSteps.map(s => s.filter)],
    opacity: [from.opacity, ...toSteps.map(s => s.opacity)],
    y: [from.y, ...toSteps.map(s => s.y)],
  }

  return (
    <span ref={ref} className={`inline-flex flex-wrap items-center ${className}`}>
      {elements.map((segment, i) => (
        <motion.span
          key={i}
          initial={from}
          animate={inView ? keyframes : from}
          transition={{ duration: totalDuration, times, delay: (i * delay) / 1000 }}
          onAnimationComplete={i === elements.length - 1 ? onAnimationComplete : undefined}
          style={{ display: 'inline-block', willChange: 'transform, filter, opacity' }}
        >
          {segment === ' ' ? '\u00A0' : segment}
          {animateBy === 'words' && i < elements.length - 1 && '\u00A0'}
        </motion.span>
      ))}
    </span>
  )
}
