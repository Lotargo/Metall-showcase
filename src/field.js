export function startField(canvas) {
  const context = canvas.getContext('2d')
  if (!context) return

  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  let visible = false
  let frame = 0
  let width = 0
  let height = 0
  const particles = Array.from({ length: 22 }, (_, row) => {
    const count = 27 + row * 6
    return Array.from({ length: count }, (_, index) => {
      const seed = Math.sin((index + row * 43) * 91.381) * 43758.54
      const jitter = seed - Math.floor(seed)
      return { distance: (row + 3) / 26, angle: index / count * Math.PI * 2 + jitter * .06, jitter }
    })
  }).flat().filter(({ jitter }) => jitter < .80)

  function paint(time = 0) {
    if (!width || !height) return
    context.clearRect(0, 0, width, height)
    const phase = time * .00038
    const radius = Math.min(width * .54, height * .47)
    context.save()
    context.translate(width * .55, height * .50)
    context.rotate(-.35)
    for (const { distance, angle, jitter } of particles) {
      const wave = Math.sin(angle * 3 - distance * 16 + phase) * .048
      const r = radius * (distance + wave)
      const x = Math.cos(angle) * r * 1.35
      const y = Math.sin(angle) * r * .87
      const envelope = Math.sin(Math.PI * distance) ** .42
      context.fillStyle = 'rgba(63, 65, 57,' + envelope * (.16 + jitter * .32) + ')'
      context.fillRect(x, y, jitter > .74 ? 2 : 1, jitter > .62 ? 4 : 1)
    }
    context.restore()
  }

  function animate(time) {
    paint(time)
    frame = requestAnimationFrame(animate)
  }

  function syncAnimation() {
    cancelAnimationFrame(frame)
    paint()
    if (visible && !reduced.matches && !document.hidden) frame = requestAnimationFrame(animate)
  }

  new ResizeObserver(([entry]) => {
    width = entry.contentRect.width
    height = entry.contentRect.height
    const ratio = Math.min(devicePixelRatio, 1.5)
    canvas.width = Math.round(width * ratio)
    canvas.height = Math.round(height * ratio)
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    paint()
  }).observe(canvas)
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    syncAnimation()
  }).observe(canvas)
  reduced.addEventListener('change', syncAnimation)
  document.addEventListener('visibilitychange', syncAnimation)
}
