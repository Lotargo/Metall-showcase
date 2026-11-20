const frameInterval = 1000 / 60

export function createFrameClock() {
  let nextFrame

  return function isFrameDue(now) {
    // Allow for fractional browser timestamps and skip any missed frames.
    const tolerance = .75
    nextFrame ??= now
    if (now + tolerance < nextFrame) return false
    const missed = Math.floor(Math.max(0, now + tolerance - nextFrame) / frameInterval)
    nextFrame += (missed + 1) * frameInterval
    return true
  }
}
