import '@fontsource-variable/manrope'
import '@fontsource-variable/commissioner/flar.css'
import '@fontsource-variable/onest'
import './style.css'

const story = document.querySelector('.model-story')
const sticky = document.querySelector('.model-sticky')
const stage = document.querySelector('.model-stage')
const slider = document.querySelector('#explode')
const header = document.querySelector('.header')
const scrollMotion = matchMedia('(prefers-reduced-motion: no-preference) and (min-height: 641px)')
let position = 0
let target = 0
let manualAt = null
let drawModel
let scrollFrame = 0
let driftFrame = 0
let lastFrame = 0

function setPosition(value) {
  position = value
  const percent = Math.round(value * 100)
  if (Number(slider.value) !== percent || slider.style.getPropertyValue('--filled') !== percent + '%') {
    slider.value = percent
    slider.style.setProperty('--filled', percent + '%')
    slider.setAttribute('aria-valuetext', percent === 0 ? 'В сборе' : percent === 100 ? 'В разборе' : percent + '% разбора')
  }
  stage.style.setProperty('--progress', value)
  drawModel?.(value)
}

function setManual(percent) {
  manualAt = window.scrollY
  cancelAnimationFrame(driftFrame)
  driftFrame = 0
  target = percent / 100
  setPosition(target)
}

function glide(now) {
  const difference = target - position
  if (Math.abs(difference) <= .002) {
    driftFrame = 0
    setPosition(target)
    return
  }
  const dt = Math.min(32, now - lastFrame)
  lastFrame = now
  setPosition(position + difference * (1 - Math.exp(-dt / 66)))
  driftFrame = requestAnimationFrame(glide)
}

function syncScroll() {
  scrollFrame = 0
  header.classList.toggle('is-scrolled', window.scrollY > 26)
  if (!scrollMotion.matches) {
    cancelAnimationFrame(driftFrame)
    driftFrame = 0
    return
  }
  if (manualAt !== null && Math.abs(manualAt - window.scrollY) < 12) return
  manualAt = null
  const travel = story.offsetHeight - sticky.offsetHeight
  if (travel <= 0) return
  const elapsed = -story.getBoundingClientRect().top
  target = Math.min(1, Math.max(0, elapsed / travel))
  if (target !== position && !driftFrame) {
    lastFrame = performance.now()
    driftFrame = requestAnimationFrame(glide)
  }
}

function requestSync() {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(syncScroll)
}

slider.addEventListener('input', () => setManual(Number(slider.value)))
document.querySelectorAll('[data-position]').forEach(button => {
  button.addEventListener('click', () => setManual(Number(button.dataset.position)))
})
window.addEventListener('scroll', requestSync, { passive: true })
window.addEventListener('resize', requestSync)
scrollMotion.addEventListener('change', requestSync)
syncScroll()

const loader = new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting) return
  loader.disconnect()
  import('./model.js')
    .then(({ mountModel }) => mountModel(document.querySelector('#model-canvas'), stage, () => position))
    .then(render => { drawModel = render })
    .catch(() => {
      // Keep the assembled and exploded Blender renders as a fallback.
    })
}, { rootMargin: '170px' })
loader.observe(stage)
