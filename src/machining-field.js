import { createFrameClock } from './frame-clock.js'

const TURN = Math.PI * 2

export function mountMachiningField(canvas) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return () => {}
  const footer = canvas.dataset.variant === 'footer'
  const motion = matchMedia('(prefers-reduced-motion: reduce)')
  const isFrameDue = createFrameClock()
  let width = 0, height = 0, frame = 0, previous = 0, elapsed = 0
  let visible = false
  let disposed = false
  canvas.setAttribute('aria-hidden', 'true')

  // Give each grain permanent coordinates so even the still frame is reproducible.
  let seed = footer ? 49157 : 72019
  function random() {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }
  const grains = []
  const rows = footer ? 32 : 28
  for (let row = 0; row < rows; row++) {
    const count = 12 + row * 5
    for (let i = 0; i < count; i++) {
      if (random() < 0.16) continue
      grains.push({
        r: (row + 1.2 + random() * 1.65) / (rows + 2),
        a: (i + random() * 1.6) / count * TURN,
        relief: random() - 0.5,
        size: 0.48 + random() ** 2 * 0.98,
        light: 0.46 + random() * 0.54,
        shape: random() * Math.PI,
      })
    }
  }

  // Small supersampled grain sprites keep the soft edge and directional glint
  // intact at fractional pixel positions, including on high-density displays.
  const sprites = Array.from({ length: 8 }, (_, index) => {
    const sprite = document.createElement('canvas')
    sprite.width = sprite.height = 24
    const brush = sprite.getContext('2d')
    brush.translate(12, 12)
    brush.rotate(index * Math.PI / 8)
    brush.scale(1, 0.61 + (index % 3) * 0.13)
    const ink = brush.createRadialGradient(-2, -2, 0, 0, 0, 10)
    ink.addColorStop(0, '#6b6c65')
    ink.addColorStop(0.44, '#363932')
    ink.addColorStop(0.72, '#4b4e46')
    ink.addColorStop(1, 'rgba(75,78,70,0)')
    brush.fillStyle = ink
    brush.fillRect(-10, -10, 20, 20)
    return sprite
  })

  function paint() {
    ctx.clearRect(0, 0, width, height)
    if (!width || !height) return
    const spanX = width * (footer ? 0.64 : 0.61)
    const spanY = height * 0.58
    const pixelScale = Math.max(0.77, Math.min(1.19, Math.sqrt(width * height / 300000)))
    for (const grain of grains) {
      const { r, a, relief } = grain
      const angle = a + elapsed * (0.028 + relief * 0.012 + (1 - r) * 0.014)
      const ripple = 3 * angle - r * 11 + elapsed * 0.20
      const radius = r + 0.034 * Math.sin(ripple)
      const u = radius * Math.cos(angle)
      const v = radius * Math.sin(angle)
      const z = 0.19 * Math.sin(ripple) + 0.09 * Math.cos(angle * 2 + r * 7) + relief * 0.11
      const depth = 0.68 * v + z
      const perspective = 1 / (1.05 - depth * 0.20)
      const x = width * 0.51 + spanX * (u + 0.20 * v) * perspective
      const y = height * 0.50 + spanY * (v - 0.39 * u - z * 0.71) * perspective
      const envelope = Math.max(0, Math.sin(Math.PI * r)) ** 0.42
      const light = 0.70 + 0.18 * Math.cos(ripple) + 0.16 * depth
      const size = (1.65 + grain.size * 1.75) * perspective ** 2 * pixelScale
      ctx.globalAlpha = Math.min(0.78, envelope * light * grain.light * (footer ? 0.95 : 0.80))
      const sprite = sprites[Math.floor(grain.shape * 8 / Math.PI)]
      ctx.drawImage(sprite, x - size / 2, y - size / 2, size, size)
    }
    ctx.globalAlpha = 1
  }
  function tick(now) {
    if (isFrameDue(now)) {
      if (previous) elapsed += Math.min(now - previous, 100) / 1000
      previous = now
      paint()
    }
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
