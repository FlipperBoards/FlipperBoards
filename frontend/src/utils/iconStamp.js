import { icon as buildIcon } from '@fortawesome/fontawesome-svg-core'

/**
 * Renders a FontAwesome icon definition into a tile code matrix.
 *
 * @param {object} iconDef     - FA icon definition from @fortawesome/free-solid-svg-icons
 * @param {number} stampCols   - Width of the stamp in tiles
 * @param {number} stampRows   - Height of the stamp in tiles
 * @param {number} fgCode      - Tile code for "lit" pixels (default 77 = white)
 * @param {number} bgCode      - Tile code for "dark" pixels (default 0 = space)
 * @param {number} threshold   - Brightness 0-255 above which a pixel is "lit" (default 96)
 * @returns {Promise<number[][]>} - stampRows × stampCols matrix of tile codes
 */
export async function renderIconToTiles(
  iconDef,
  stampCols,
  stampRows,
  fgCode = 77,
  bgCode = 0,
  threshold = 96,
) {
  const rendered = buildIcon(iconDef)
  if (!rendered) throw new Error(`Could not render icon: ${iconDef?.iconName}`)

  let svgString = rendered.html[0]
    .replace(/fill="currentColor"/g, 'fill="white"')
    .replace(/fill:currentColor/g, 'fill:white')

  // Inject explicit dimensions and preserve aspect ratio
  const scale = 16
  const w = stampCols * scale
  const h = stampRows * scale
  svgString = svgString
    .replace(/<svg /, `<svg width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet" `)

  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)

  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = 'black'
      ctx.fillRect(0, 0, w, h)
      ctx.drawImage(img, 0, 0, w, h)
      URL.revokeObjectURL(url)

      const imageData = ctx.getImageData(0, 0, w, h)
      const pixels = imageData.data

      const result = []
      for (let r = 0; r < stampRows; r++) {
        const row = []
        for (let c = 0; c < stampCols; c++) {
          let total = 0
          for (let py = r * scale; py < (r + 1) * scale; py++) {
            for (let px = c * scale; px < (c + 1) * scale; px++) {
              const idx = (py * w + px) * 4
              // Perceived luminance
              total += pixels[idx] * 0.299 + pixels[idx + 1] * 0.587 + pixels[idx + 2] * 0.114
            }
          }
          const avg = total / (scale * scale)
          row.push(avg >= threshold ? fgCode : bgCode)
        }
        result.push(row)
      }
      resolve(result)
    }
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e) }
    img.src = url
  })
}
