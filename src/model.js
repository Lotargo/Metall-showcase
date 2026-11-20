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
  renderer.toneMappingExposure = 1.04
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-4, 4, 3, -3, .1, 100)

  const room = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  const environment = pmrem.fromScene(room, .03)
  room.dispose()
  pmrem.dispose()
  scene.environment = environment.texture
  scene.environmentIntensity = 1.12

  for (const [position, intensity] of [[[3, 5, 3], 2.15], [[-3, -2, -2], 1.5]]) {
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

  const strip = document.createElement('canvas')
  strip.width = 4
  strip.height = 512
  const brush = strip.getContext('2d')
  for (let y = 0; y < strip.height; y++) {
    const tone = Math.round(135 + 70 * Math.sin(y * 23.2) + 40 * Math.sin(y * 6.3))
    brush.fillStyle = 'rgb(' + tone + ' ' + tone + ' ' + tone + ')'
    brush.fillRect(0, y, 4, 1)
  }
  const grain = new THREE.CanvasTexture(strip)
  const moving = []
  assembly.traverse(node => {
    if (typeof node.userData.travel === 'number') moving.push(node)
    if (node.isMesh && node.material.name === 'Turned steel') {
      node.material.bumpMap = grain
      node.material.bumpScale = .015
    }
  })
  scene.add(assembly)

  let lost = false
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  function render(progress) {
    if (lost || !host.clientWidth || !host.clientHeight) return
    const easing = progress * progress * (3 - 2 * progress)
    for (const part of moving) part.position.y = part.userData.travel * easing
    const rotation = reduced.matches ? 0 : easing
    camera.position.set(8 - 2.6 * rotation, -7 + 1.7 * rotation, 11)
    camera.lookAt(0, -.21 * easing, 0)
    camera.rotateZ(-1.065 + .085 * rotation)
    const aspect = host.clientWidth / host.clientHeight
    const height = Math.max(4.15 + 1.35 * easing, (7.25 + 4.80 * easing) / aspect)
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
