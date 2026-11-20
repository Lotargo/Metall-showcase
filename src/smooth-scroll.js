import { createFrameClock } from './frame-clock.js'

const response = 15

export function enableSmoothScroll(reducedMotion) {
  const isFrameDue = createFrameClock()
  let frame = 0
  let current = 0
  let target = 0
  let velocity = 0
  let lastScroll = 0
  let lastFrame = 0

  function stop() {
    cancelAnimationFrame(frame)
    frame = 0
    velocity = 0
  }

  function advance(now) {
    if (Math.abs(window.scrollY - lastScroll) > 1) {
      stop()
      return
    }
    if (!isFrameDue(now)) {
      frame = requestAnimationFrame(advance)
      return
    }

    const duration = Math.max(0, Math.min(now - lastFrame, 48)) / 1000
    lastFrame = now

    // A critically damped spring carries velocity through each wheel notch.
    const offset = current - target
    const motion = velocity + response * offset
    const decay = Math.exp(-response * duration)
    current = target + (offset + motion * duration) * decay
    velocity = (velocity - response * motion * duration) * decay

    const settled = Math.abs(current - target) <= .75 && Math.abs(velocity) <= 8
    if (settled) current = target
    window.scrollTo({ top: current, behavior: 'instant' })
    lastScroll = window.scrollY
    if (settled) stop()
    else frame = requestAnimationFrame(advance)
  }

  function onWheel(event) {
    if (reducedMotion.matches || event.defaultPrevented || !event.cancelable ||
        event.ctrlKey || event.shiftKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY) ||
        event.target.closest?.('input, select, textarea, [contenteditable]')) return

    const { clientHeight, scrollHeight } = document.scrollingElement
    const limit = Math.max(0, scrollHeight - clientHeight)
    if (frame && Math.abs(window.scrollY - lastScroll) > 1) stop()
    if (!frame) current = target = lastScroll = window.scrollY
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? clientHeight : 1
    const next = Math.max(0, Math.min(limit, target + event.deltaY * unit))
    if (next === target && !frame) return

    event.preventDefault()
    target = next
    if (!frame) {
      lastFrame = performance.now()
      frame = requestAnimationFrame(advance)
    }
  }

  window.addEventListener('wheel', onWheel, { passive: false })
  window.addEventListener('pointerdown', stop, { passive: true })
  window.addEventListener('keydown', stop)
  document.addEventListener('visibilitychange', stop)
  reducedMotion.addEventListener('change', stop)
}
