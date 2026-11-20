import '@fontsource-variable/golos-text'
import '@fontsource/ibm-plex-mono/cyrillic-400.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import './style.css'
import { startField } from './field.js'

const story = document.querySelector('.model-story')
const sticky = document.querySelector('.model-sticky')
const stage = document.querySelector('.model-stage')
const slider = document.querySelector('#explode')
const header = document.querySelector('.header')
const scrollMotion = matchMedia('(prefers-reduced-motion: no-preference) and (min-height: 641px)')
let position = 0
let manualAt = null
let drawModel
let pending = false

function setPosition(value) {
  position = value
  const percent = Math.round(value * 100)
  slider.value = percent
  slider.style.setProperty('--filled', percent + '%')
  slider.setAttribute('aria-valuetext', percent === 0 ? 'В сборе' : percent === 100 ? 'В разборе' : percent + '% разбора')
  stage.style.setProperty('--progress', value)
  drawModel?.(value)
}

function setManual(percent) {
  manualAt = window.scrollY
  setPosition(percent / 100)
}

function syncScroll() {
  pending = false
  header.classList.toggle('is-scrolled', window.scrollY > 20)
  if (!scrollMotion.matches) return
  if (manualAt !== null && Math.abs(manualAt - window.scrollY) < 12) return
  manualAt = null
  const travel = story.offsetHeight - sticky.offsetHeight
  if (travel <= 0) return
  const elapsed = -story.getBoundingClientRect().top
  const progress = Math.min(1, Math.max(0, elapsed / travel))
  if (progress !== position) setPosition(progress)
}

function requestSync() {
  if (pending) return
  pending = true
  requestAnimationFrame(syncScroll)
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
      // The two Blender renders stay available as a fallback.
    })
}, { rootMargin: '200px' })
loader.observe(stage)

startField(document.querySelector('#field'))
