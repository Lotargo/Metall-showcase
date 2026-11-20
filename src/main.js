import '@fontsource-variable/manrope'
import '@fontsource-variable/commissioner/flar.css'
import '@fontsource-variable/onest'
import { createFrameClock } from './frame-clock.js'
import { mountMachiningField } from './machining-field.js'
import { enableSmoothScroll } from './smooth-scroll.js'
import './style.css'

document.querySelectorAll('[data-machining-field]').forEach(mountMachiningField)

const header = document.querySelector('.header')
const rootStyle = document.documentElement.style
function syncHeaderHeight() {
  const height = `${header.offsetHeight}px`
  if (rootStyle.getPropertyValue('--header-height') !== height) rootStyle.setProperty('--header-height', height)
}
syncHeaderHeight()
new ResizeObserver(syncHeaderHeight).observe(header)

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')
enableSmoothScroll(reducedMotion)
if (!reducedMotion.matches && 'IntersectionObserver' in window) {
  const belowFold = [...document.querySelectorAll('[data-reveal]')]
    .filter(block => block.getBoundingClientRect().top >= window.innerHeight)
  const reveals = new IntersectionObserver(entries => {
    for (const { target, isIntersecting } of entries) {
      if (!isIntersecting) continue
      target.classList.remove('reveal-pending')
      reveals.unobserve(target)
    }
  }, { rootMargin: '0px 0px -48px 0px' })
  for (const block of belowFold) {
    block.classList.add('reveal-pending')
    reveals.observe(block)
  }
}

const story = document.querySelector('.model-story')
const sticky = document.querySelector('.model-sticky')
const stage = document.querySelector('.model-stage')
const slider = document.querySelector('#explode')
const modelControl = slider.parentElement
const scrollMotion = matchMedia('(prefers-reduced-motion: no-preference) and (min-height: 641px)')
const isModelFrameDue = createFrameClock()
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
  const fill = percent + '%'
  if (Number(slider.value) !== percent || modelControl.style.getPropertyValue('--filled') !== fill) {
    slider.value = percent
    modelControl.style.setProperty('--filled', fill)
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
  if (!isModelFrameDue(now)) {
    driftFrame = requestAnimationFrame(glide)
    return
  }
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
  const elapsed = sticky.getBoundingClientRect().top - story.getBoundingClientRect().top
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

const machiningStage = document.querySelector('.machining-stage')
const machiningPoster = machiningStage.querySelector('.machining-poster')
const machiningCanvas = machiningStage.querySelector('.machining-canvas')
const stageControls = document.querySelector('.stage-controls')
const selectedStage = () => stageControls.querySelector('input:checked')
let drawMachiningStage

function syncMachiningStage() {
  const option = selectedStage()
  machiningStage.setAttribute('aria-label', option.dataset.summary)
  machiningPoster.src = import.meta.env.BASE_URL + 'media/machining-' + option.value + '.webp'
  drawMachiningStage?.(option.value)
}

stageControls.addEventListener('change', syncMachiningStage)
syncMachiningStage()

const machiningLoader = new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting) return
  machiningLoader.disconnect()
  import('./model.js')
    .then(({ mountMachiningStages }) => mountMachiningStages(machiningCanvas, machiningStage, () => selectedStage().value))
    .then(render => { drawMachiningStage = render })
    .catch(() => {
      // Keep the selected Blender render if the live model cannot load.
    })
}, { rootMargin: '170px' })
machiningLoader.observe(machiningStage)
