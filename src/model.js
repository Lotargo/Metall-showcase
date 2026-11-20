import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

export async function mountModel(host, stage, getPosition) {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('webgl2', { alpha: true, antialias: true })
  if (!context) return

  const renderer = new THREE.WebGLRenderer({ canvas, context, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = .94
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-4, 4, 3, -3, .1, 100)

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
