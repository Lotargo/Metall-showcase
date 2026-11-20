import { createFrameClock } from './frame-clock.js'

const response = 15
const gesturePause = 150
const scrollKeys = new Set(['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', ' '])

export function enableSmoothScroll(reducedMotion) {
  const isFrameDue = createFrameClock()
  const sections = [...document.querySelectorAll('main > section')]
  const initialSection = sections.find(section => section.id && `#${section.id}` === window.location.hash)
  if (initialSection && performance.getEntriesByType('navigation')[0]?.type === 'navigate') {
    initialSection.scrollIntoView({ behavior: 'instant' })
  }
  let frame = 0
  let current = 0
  let target = 0
  let velocity = 0
  let lastScroll = 0
  let lastFrame = 0
  let wheelTimer = 0
  let wheelStart = 0
  let wheelDirection = 0
  let nativeStart = null
  let nativeTimer = 0

  function stop() {
    cancelAnimationFrame(frame)
    frame = 0
    velocity = 0
  }

  function cancel() {
    stop()
    clearTimeout(wheelTimer)
    clearTimeout(nativeTimer)
    wheelTimer = 0
    nativeStart = null
  }

  function advance(now) {
    if (Math.abs(window.scrollY - lastScroll) > 1) {
      cancel()
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

  function setTarget(next) {
    target = next
    if (frame) return
    current = lastScroll = window.scrollY
    lastFrame = performance.now()
    frame = requestAnimationFrame(advance)
  }

  function sectionLanding(end, start) {
    const direction = Math.sign(end - start)
    const { clientHeight, scrollHeight } = document.scrollingElement
    const inset = Number.parseFloat(getComputedStyle(document.documentElement).scrollPaddingBlockStart) || 0
    const limit = Math.max(0, scrollHeight - clientHeight)
    const scroll = window.scrollY
    const points = [0, limit, ...sections.map(section => scroll + section.getBoundingClientRect().top - inset)]
    let landing = end
    let distance = Math.min(260, clientHeight * .25)

    for (const point of points) {
      const top = Math.max(0, Math.min(limit, point))
      const gap = Math.abs(top - end)
      // Only dock to a boundary in the direction of travel, so small wheel steps can leave it.
      if ((top - start) * direction <= 2 || gap >= distance) continue
      landing = top
      distance = gap
    }
    return landing
  }

  function finishWheel() {
    wheelTimer = 0
    const landing = sectionLanding(target, wheelStart)
    if (Math.abs(landing - target) > 1) setTarget(landing)
  }

  function onWheel(event) {
    if (reducedMotion.matches || event.defaultPrevented || !event.cancelable ||
        event.ctrlKey || event.shiftKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY) ||
        event.target.closest?.('input, select, textarea, [contenteditable]')) return

    nativeStart = null
    const { clientHeight, scrollHeight } = document.scrollingElement
    const limit = Math.max(0, scrollHeight - clientHeight)
    if (frame && Math.abs(window.scrollY - lastScroll) > 1) cancel()
    if (!frame) target = window.scrollY
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? clientHeight : 1
    const next = Math.max(0, Math.min(limit, target + event.deltaY * unit))
    if (next === target && !frame) return

    event.preventDefault()
    const direction = Math.sign(event.deltaY)
    if (!wheelTimer || direction !== wheelDirection) wheelStart = target
    wheelDirection = direction
    clearTimeout(wheelTimer)
    wheelTimer = setTimeout(finishWheel, gesturePause)
    setTarget(next)
  }

  function finishNative() {
    const start = nativeStart
    nativeStart = null
    if (start === null || reducedMotion.matches) return
    const scroll = window.scrollY
    const landing = sectionLanding(scroll, start)
    if (Math.abs(landing - scroll) > 1) window.scrollTo({ top: landing, behavior: 'smooth' })
  }

  window.addEventListener('wheel', onWheel, { passive: false })
  window.addEventListener('pointerdown', event => {
    cancel()
    if (event.pointerType === 'touch' && event.isPrimary && !reducedMotion.matches &&
        !event.target.closest?.('a, button, input, select, textarea, [contenteditable]')) nativeStart = window.scrollY
  }, { passive: true })
  window.addEventListener('keydown', event => {
    cancel()
    if (scrollKeys.has(event.key) && !event.defaultPrevented && !event.altKey && !event.ctrlKey && !event.metaKey &&
        !reducedMotion.matches && !event.target.closest?.('button, input, select, textarea, [contenteditable]')) nativeStart = window.scrollY
  })
  if ('onscrollend' in document) document.addEventListener('scrollend', finishNative)
  else window.addEventListener('scroll', () => {
    if (nativeStart === null) return
    clearTimeout(nativeTimer)
    nativeTimer = setTimeout(finishNative, gesturePause)
  }, { passive: true })
  window.addEventListener('hashchange', cancel)
  document.addEventListener('visibilitychange', cancel)
  reducedMotion.addEventListener('change', cancel)
}
