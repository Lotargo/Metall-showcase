import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

function createModelScene(canvas, context) {
  const renderer = new THREE.WebGLRenderer({ canvas, context, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = .94
  const scene = new THREE.Scene()

  const room = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  const environment = pmrem.fromScene(room, .03)
  room.dispose()
  pmrem.dispose()
  scene.environment = environment.texture
  scene.environmentIntensity = .94

  for (const [position, intensity] of [[[3, 5, 3], 1.65], [[-3, -2, -2], 1.12]]) {
    const light = new THREE.DirectionalLight(0xffffff, intensity)
    light.position.set(...position)
    scene.add(light)
  }

  return { renderer, scene, environment }
}

export async function mountModel(host, stage, getPosition) {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('webgl2', { alpha: true, antialias: true })
  if (!context) return

  const { renderer, scene, environment } = createModelScene(canvas, context)
  const camera = new THREE.OrthographicCamera(-4, 4, 3, -3, .1, 100)
  let assembly
  try {
    assembly = (await new GLTFLoader().loadAsync(import.meta.env.BASE_URL + 'media/shaft.glb')).scene
  } catch (error) {
    environment.dispose()
    renderer.dispose()
    throw error
  }

  const moving = []
  assembly.traverse(node => {
    if (typeof node.userData.travel === 'number') moving.push(node)
  })
  scene.add(assembly)

  let lost = false
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  function render(progress) {
    if (lost || !host.clientWidth || !host.clientHeight) return
    const easing = progress * progress * (3 - 2 * progress)
    for (const part of moving) part.position.y = part.userData.travel * easing
    const rotation = reduced.matches ? 0 : easing
    camera.position.set(8 - rotation, -7 + 1.5 * rotation, 11 + 3 * rotation)
    camera.lookAt(0, -.02 + .45 * easing, 0)
    camera.rotateZ(THREE.MathUtils.degToRad(-61 - 4 * rotation))
    const aspect = host.clientWidth / host.clientHeight
    const height = Math.max(4.8 + 2.4 * easing, (7.65 + 6.55 * easing) / aspect)
    camera.left = -height * aspect / 2
    camera.right = height * aspect / 2
    camera.top = height / 2
    camera.bottom = -height / 2
    camera.updateProjectionMatrix()
    renderer.render(scene, camera)
  }

  function resize() {
    renderer.setSize(host.clientWidth, host.clientHeight)
    render(getPosition())
  }

  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault()
    lost = true
    canvas.hidden = true
    stage.classList.remove('is-live')
  })
  canvas.addEventListener('webglcontextrestored', () => {
    lost = false
    canvas.hidden = false
    resize()
    stage.classList.add('is-live')
  })
  host.append(canvas)
  resize()
  stage.classList.add('is-live')
  new ResizeObserver(resize).observe(host)
  reduced.addEventListener('change', () => render(getPosition()))
  return render
}

export async function mountMachiningStages(host, stage, getStage) {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('webgl2', { alpha: true, antialias: true })
  if (!context) return

  const { renderer, scene, environment } = createModelScene(canvas, context)
  let models
  try {
    const stages = (await new GLTFLoader().loadAsync(import.meta.env.BASE_URL + 'media/machining-stages.glb')).scene
    models = ['blank', 'rough', 'finished'].map(name => stages.getObjectByName(name))
    if (models.some(model => !model)) throw new Error('Missing geometry for a machining stage')
    scene.add(stages)
  } catch (error) {
    environment.dispose()
    renderer.dispose()
    throw error
  }

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 100)
  camera.position.set(8, 8, 13)
  camera.lookAt(0, 0, 0)
  // Match the Blender poster camera and preserve its framing when the panel resizes.
  const posterWidth = 8.15
  const posterHeight = posterWidth * 790 / 1400
  let lost = false

  function render(selected) {
    if (lost || !host.clientWidth || !host.clientHeight) return
    for (const model of models) model.visible = model.name === selected
    renderer.render(scene, camera)
  }

  function resize() {
    const { clientWidth: width, clientHeight: height } = host
    if (!width || !height || lost) return
    renderer.setSize(width, height)
    const aspect = width / height
    const viewHeight = Math.max(posterHeight, posterWidth / aspect)
    camera.left = -viewHeight * aspect / 2
    camera.right = viewHeight * aspect / 2
    camera.top = viewHeight / 2
    camera.bottom = -viewHeight / 2
    camera.updateProjectionMatrix()
    render(getStage())
  }

  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault()
    lost = true
    canvas.hidden = true
    stage.classList.remove('is-live')
  })
  canvas.addEventListener('webglcontextrestored', () => {
    lost = false
    canvas.hidden = false
    resize()
    stage.classList.add('is-live')
  })
  host.append(canvas)
  resize()
  stage.classList.add('is-live')
  new ResizeObserver(resize).observe(host)
  return render
}
