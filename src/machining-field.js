const TURN = Math.PI * 2

export function mountMachiningField(canvas) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return () => {}
  const footer = canvas.dataset.variant === 'footer'
  const motion = matchMedia('(prefers-reduced-motion: reduce)')
  let width = 0, height = 0, frame = 0, previous = 0, elapsed = 0
  let visible = false
  let disposed = false
  canvas.setAttribute('aria-hidden', 'true')

  function paint() {
    ctx.clearRect(0, 0, width, height)
    if (!width || !height) return
    const scale = Math.min(width * 0.72, height * 1.18)
    ctx.save()
    ctx.translate(width * (footer ? 0.64 : 0.56), height * (footer ? 0.54 : 0.53))
    ctx.rotate(footer ? -0.36 : -0.48)
    ctx.strokeStyle = '#292a27'
    ctx.lineWidth = Math.max(0.85, Math.min(1.35, scale / 450))
    const rows = footer ? 26 : 20
    for (let row = 0; row < rows; row++) {
      const feed = row / (rows - 1)
      const rx = scale * (0.38 + feed * 0.54)
      const ry = rx * (footer ? 0.43 : 0.53)
      const offset = (feed - 0.5) * scale * 0.31
      const count = 46 + row
      const step = TURN / count
      const rotation = elapsed * (0.065 + 0.019 * feed) + feed * 0.74
      ctx.globalAlpha = (footer ? 0.46 : 0.32) * (0.62 + 0.38 * Math.sin(Math.PI * feed))
      ctx.beginPath()
      for (let tooth = 0; tooth < count; tooth++) {
        const angle = step * tooth + rotation
        const ridge = Math.cos(2 * angle - feed * 4.3 - elapsed * 0.095)
        const engagement = Math.max(0, ridge * 0.71 + 0.4 + 0.2 * Math.sin(angle * 3 + feed * 6))
        const length = step * engagement * 0.77
        if (length * ry < 1.8) continue
        const finish = angle + length
        ctx.moveTo(offset + rx * Math.cos(angle), ry * Math.sin(angle))
        ctx.lineTo(offset + rx * Math.cos(finish), ry * Math.sin(finish))
      }
      ctx.stroke()
    }
    ctx.restore()
  }

  function tick(now) {
    if (previous) elapsed += Math.min(now - previous, 100) / 1000
    previous = now
    paint()
    frame = requestAnimationFrame(tick)
  }

  function sync() {
    cancelAnimationFrame(frame)
    previous = 0
    if (disposed || document.hidden || !visible || !width || !height) return
    if (motion.matches) {
      elapsed = 0
      paint()
    } else {
      frame = requestAnimationFrame(tick)
    }
  }

  function resize() {
    const rect = canvas.getBoundingClientRect()
    width = rect.width
    height = rect.height
    const density = Math.min(devicePixelRatio || 1, 2)
    canvas.width = Math.round(width * density)
    canvas.height = Math.round(height * density)
    ctx.setTransform(density, 0, 0, density, 0, 0)
    sync()
  }

  const bounds = new ResizeObserver(resize)
  const viewport = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    sync()
  })
  bounds.observe(canvas)
  viewport.observe(canvas)
  motion.addEventListener('change', sync)
  document.addEventListener('visibilitychange', sync)
  window.addEventListener('resize', resize)
  return () => {
    disposed = true
    cancelAnimationFrame(frame)
    viewport.disconnect()
    bounds.disconnect()
    window.removeEventListener('resize', resize)
    document.removeEventListener('visibilitychange', sync)
    motion.removeEventListener('change', sync)
  }
}
