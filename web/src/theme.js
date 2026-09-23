const clone = value => {
  if (Array.isArray(value)) return value.map(clone)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, clone(v)]))
  return value
}

function merge(base, overrides = {}) {
  const out = clone(base)
  for (const [key, value] of Object.entries(overrides)) {
    if (value && typeof value === 'object' && !Array.isArray(value) && out[key] && typeof out[key] === 'object' && !Array.isArray(out[key])) {
      out[key] = merge(out[key], value)
    } else {
      out[key] = clone(value)
    }
  }
  return out
}

export const MANIM = Object.freeze({
  name: 'manim',
  canvas: Object.freeze({
    width: 1920,
    height: 1080,
    unitSize: 135,
    fps: 60,
    background: '#000000',
  }),
  style: Object.freeze({
    fill: null,
    stroke: '#ffffff',
    strokeWidth: 4 / 135,
  }),
  text: Object.freeze({
    fontSize: 48,
    color: '#ffffff',
    fontFamily: 'Inter, ui-sans-serif, system-ui',
  }),
  math: Object.freeze({
    fontSize: 48,
    color: '#ffffff',
  }),
  animation: Object.freeze({
    duration: 1,
    waitDuration: 1,
    easing: 'smooth',
  }),
  shape: Object.freeze({
    dotRadius: 0.08,
    arrowTipLength: 0.35,
    arrowTipWidth: 0.35,
    arrowBuff: 0.25,
  }),
  mesh3dColor: '#58c4dd',
})

const CONFIG_KEY_MAP = Object.freeze({
  canvas: { unit_size: 'unitSize' },
  style: { stroke_width: 'strokeWidth' },
  text: { font_size: 'fontSize', font: 'fontFamily' },
  math: { font_size: 'fontSize', font: 'fontFamily' },
  animation: { wait_duration: 'waitDuration' },
  shape: {
    dot_radius: 'dotRadius',
    arrow_tip_length: 'arrowTipLength',
    arrow_tip_width: 'arrowTipWidth',
    arrow_buff: 'arrowBuff',
  },
})

function configOverrides(raw) {
  const out = {}
  for (const [key, value] of Object.entries(raw)) {
    if (key === 'base') continue
    if (key === 'mesh3d_color') { out.mesh3dColor = value; continue }
    if (value && typeof value === 'object' && !Array.isArray(value) && CONFIG_KEY_MAP[key]) {
      out[key] = {}
      for (const [subkey, subvalue] of Object.entries(value)) {
        out[key][CONFIG_KEY_MAP[key][subkey] ?? subkey] = subvalue
      }
      continue
    }
    out[key] = value
  }
  return out
}

function validateTheme(theme) {
  if (!theme || typeof theme !== 'object' || !theme.name) throw new TypeError('theme must be an object with a name')
  const { canvas, style, text, math, animation, shape } = theme
  if (!(canvas?.width > 0 && canvas?.height > 0 && canvas?.unitSize > 0 && canvas?.fps > 0)) throw new RangeError('theme canvas dimensions, unitSize and fps must be positive')
  if (!(style?.strokeWidth >= 0)) throw new RangeError('theme strokeWidth must be >= 0')
  if (!(text?.fontSize > 0 && math?.fontSize > 0)) throw new RangeError('theme fontSize must be positive')
  if (!(animation?.duration >= 0 && animation?.waitDuration >= 0)) throw new RangeError('theme animation durations must be >= 0')
  if (!['linear', 'smoothstep', 'smooth'].includes(animation?.easing)) throw new RangeError('theme easing must be linear, smoothstep, or smooth')
  if (!(shape?.dotRadius > 0 && shape?.arrowTipLength >= 0 && shape?.arrowTipWidth >= 0 && shape?.arrowBuff >= 0)) throw new RangeError('theme shape dimensions are invalid')
  if (theme.mesh3dColor == null) throw new TypeError('theme mesh3dColor is required')
  return theme
}

const themes = new Map([[MANIM.name, MANIM]])
let currentTheme = MANIM

export function registerTheme(theme, { replace = false } = {}) {
  validateTheme(theme)
  if (themes.has(theme.name) && !replace) throw new Error(`theme ${theme.name} is already registered`)
  themes.set(theme.name, theme)
  return theme
}

export function themeNamed(name) {
  const theme = themes.get(String(name))
  if (!theme) throw new Error(`unknown Zanim theme ${name}; available: ${[...themes.keys()].sort().join(', ')}`)
  return theme
}

export function getTheme() { return currentTheme }

export function setTheme(theme) {
  const resolved = typeof theme === 'string' ? themeNamed(theme) : theme
  validateTheme(resolved)
  currentTheme = resolved
  return resolved
}

export function createTheme(base = 'manim', overrides = {}) {
  const resolved = typeof base === 'string' ? themeNamed(base) : base
  const theme = merge(resolved, overrides)
  theme.name = overrides.name ?? resolved.name
  return validateTheme(theme)
}

export function configFromObject(config = {}) {
  const raw = config.theme ?? 'manim'
  if (typeof raw === 'string') return { theme: themeNamed(raw) }
  if (!raw || typeof raw !== 'object') throw new TypeError('config theme must be a theme name or object')
  const { base = 'manim' } = raw
  return { theme: createTheme(base, configOverrides(raw)) }
}

export async function loadConfig(source) {
  if (source && typeof source === 'object') return configFromObject(source)
  if (typeof source !== 'string') throw new TypeError('config source must be an object or JSON URL')
  const response = await fetch(source)
  if (!response.ok) throw new Error(`failed to load Zanim config: ${response.status} ${response.statusText}`)
  return configFromObject(await response.json())
}

export async function applyConfig(source) {
  const config = source?.theme && typeof source.theme === 'object' && source.theme.name && source.theme.canvas && source.theme.style && source.theme.animation
    ? source
    : await loadConfig(source)
  setTheme(config.theme)
  return config
}
