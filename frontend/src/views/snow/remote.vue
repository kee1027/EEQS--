<template>
  <div class="whiterisk-theme">
    <header class="page-header">
      <nav class="breadcrumb">积雪动态 / 遥感</nav>
      <h1>MODIS 积雪遥感监测</h1>
      <p class="page-desc">基于 MOD10A1 NDSI 数据的阿勒泰地区积雪覆盖分布 — 实时瓦片服务</p>
    </header>

    <main class="dashboard-content">
      <!-- 统计卡片 -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e0f3f8; color: #2c7fb8;">📅</div>
          <div class="stat-info">
            <div class="stat-value">{{ latestDate || '--' }}</div>
            <div class="stat-label">数据日期</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: #fee090; color: #d95f0e;">🛰️</div>
          <div class="stat-info">
            <div class="stat-value">MOD10A1</div>
            <div class="stat-label">数据产品</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: #fdae61; color: #a63603;">📐</div>
          <div class="stat-info">
            <div class="stat-value">500m</div>
            <div class="stat-label">空间分辨率</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: #f46d43; color: #7f2704;">🗺️</div>
          <div class="stat-info">
            <div class="stat-value">h23v04+h24v04</div>
            <div class="stat-label">覆盖瓦片</div>
          </div>
        </div>
      </div>

      <!-- 主地图展示区 -->
      <div class="main-visual">
        <div class="visual-card">
          <div class="card-header">
            <h3>阿勒泰地区积雪覆盖分布</h3>
            <div class="card-tags">
              <span class="tag">NDSI Snow Cover</span>
              <span class="tag">EPSG:4326</span>
            </div>
          </div>
          <div class="map-container-wrapper">
            <div id="snow-map-container" class="snow-map" />

            <!-- 图例 -->
            <div class="map-legend">
              <div class="legend-title">积雪覆盖率 (NDSI)</div>
              <div v-for="item in NDSI_LEGEND" :key="item.range" class="legend-item">
                <span class="legend-swatch" :style="{ background: item.color }" />
                <span class="legend-range">{{ item.range }}</span>
              </div>
              <div class="legend-note">透明 = 无数据 / 云 / 水体</div>
            </div>

            <!-- 透明度控制 -->
            <div class="map-opacity-control">
              <div class="opacity-label">图层透明度</div>
              <el-slider
                v-model="snowOpacity"
                :min="0"
                :max="100"
                :show-tooltip="false"
                @input="handleOpacityChange"
              />
              <div class="opacity-value">{{ snowOpacity }}%</div>
            </div>
          </div>
        </div>

        <!-- 侧边信息面板 -->
        <div class="side-panel">
          <div class="info-card">
            <h4>🎨 积雪覆盖分级</h4>
            <div class="legend-list">
              <div class="legend-item">
                <span class="legend-color" style="background: #e0f3f8;" />
                <span class="legend-label">0% ~ 20%</span>
                <span class="legend-desc">无积雪/微量</span>
              </div>
              <div class="legend-item">
                <span class="legend-color" style="background: #74add1;" />
                <span class="legend-label">20% ~ 40%</span>
                <span class="legend-desc">低覆盖</span>
              </div>
              <div class="legend-item">
                <span class="legend-color" style="background: #fee090;" />
                <span class="legend-label">40% ~ 60%</span>
                <span class="legend-desc">中低覆盖</span>
              </div>
              <div class="legend-item">
                <span class="legend-color" style="background: #fdae61;" />
                <span class="legend-label">60% ~ 80%</span>
                <span class="legend-desc">中高覆盖</span>
              </div>
              <div class="legend-item">
                <span class="legend-color" style="background: #f46d43;" />
                <span class="legend-label">80% ~ 100%</span>
                <span class="legend-desc">高覆盖</span>
              </div>
            </div>
          </div>

          <div class="info-card">
            <h4>📍 空间范围</h4>
            <div class="range-info">
              <div class="range-row">
                <span class="range-key">经度</span>
                <span class="range-val">85.5°E ~ 91.1°E</span>
              </div>
              <div class="range-row">
                <span class="range-key">纬度</span>
                <span class="range-val">45.0°N ~ 49.2°N</span>
              </div>
              <div class="range-row">
                <span class="range-key">中心区域</span>
                <span class="range-val">阿勒泰地区</span>
              </div>
            </div>
          </div>

          <div class="info-card">
            <h4>📋 数据状态</h4>
            <div class="data-status">
              <div class="status-row">
                <span class="status-key">最新数据</span>
                <span class="status-val">{{ latestDate || '--' }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">更新方式</span>
                <span class="status-val">每日 02:20 自动追新</span>
              </div>
              <div class="status-row">
                <span class="status-key">瓦片缩放</span>
                <span class="status-val">z6 ~ z11</span>
              </div>
            </div>
            <el-button
              size="small"
              type="primary"
              style="margin-top: 12px; width: 100%;"
              :loading="refreshLoading"
              @click="handleRefresh"
            >
              {{ refreshLoading ? '更新中...' : '手动刷新数据' }}
            </el-button>
          </div>

          <div class="info-card">
            <h4>📖 数据说明</h4>
            <ul class="data-notes">
              <li>数据来源于 MODIS Terra 卫星 MOD10A1 产品</li>
              <li>采用 NDSI（归一化差分积雪指数）算法反演</li>
              <li>已过滤云和水体掩膜（无效值已剔除）</li>
              <li>两景影像（h23v04 + h24v04）无缝拼接</li>
              <li>从正弦投影重投影至 WGS84 坐标系</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import proj4 from 'proj4'
import request from '@/utils/request'

proj4.defs('LCC', '+proj=lcc +lat_1=30 +lat_2=60 +lat_0=0 +lon_0=100 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')

// 阿勒泰区域常量
const ALTAY_BOUNDS = L.latLngBounds([[45.0, 85.5], [49.2, 91.1]])
const ALTAY_CENTER = [47.1, 88.3]

const NDSI_LEGEND = [
  { range: '0% ~ 20%', color: '#e0f3f8' },
  { range: '20% ~ 40%', color: '#74add1' },
  { range: '40% ~ 60%', color: '#fee090' },
  { range: '60% ~ 80%', color: '#fdae61' },
  { range: '80% ~ 100%', color: '#f46d43' }
]

export default {
  name: 'SnowRemote',
  data() {
    return {
      map: null,
      snowLayer: null,
      baseLayer: null,
      snowOpacity: 80,
      NDSI_LEGEND,
      latestDate: '',
      refreshLoading: false,
      pollTimer: null
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.initMap()
      this.fetchLatestDate()
    })
  },
  beforeDestroy() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
    }
    if (this.map) {
      this.map.remove()
      this.map = null
    }
  },
  methods: {
    initMap() {
      // 初始化地图
      this.map = L.map('snow-map-container', {
        center: ALTAY_CENTER,
        zoom: 8,
        zoomControl: true,
        attributionControl: false
      })

      // 底图（现有瓦片服务）
      this.baseLayer = L.tileLayer('/api/tiles/default/{z}/{x}/{y}.png', {
        minZoom: 7,
        maxZoom: 14
      }).addTo(this.map)

      // 流域轮廓（固定黑色边界，置顶展示，不受透明度控制）
      this.loadWatershedOutline()

      // 积雪图层（半透明叠加，无数据区天然透明）
      this.snowLayer = L.tileLayer('/api/tiles/modis-snow/{z}/{x}/{y}.png', {
        minZoom: 6,
        maxZoom: 11,
        opacity: this.snowOpacity / 100
      }).addTo(this.map)

      // 视野限制在数据区域附近
      const paddedBounds = ALTAY_BOUNDS.pad(0.5)
      this.map.setMaxBounds(paddedBounds)

      // 添加比例尺
      L.control.scale({ position: 'bottomright', metric: true, imperial: false }).addTo(this.map)
    },

    async loadWatershedOutline() {
      try {
        const response = await fetch('/json/output.geojson')
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        if (data && data.features) {
          data.features.forEach(feature => {
            if (!feature.geometry || !feature.geometry.coordinates) return
            const coords = feature.geometry.coordinates[0]
            if (!Array.isArray(coords)) return
            feature.geometry.coordinates[0] = coords.map(point => {
              const [lon, lat] = proj4('LCC', 'WGS84', point)
              return [lon, lat]
            })
          })
        }

        const outlineLayer = L.geoJSON(data, {
          style: {
            color: '#000000',
            weight: 2,
            opacity: 1,
            fillColor: '#000000',
            fillOpacity: 0
          }
        }).addTo(this.map)

        outlineLayer.bringToFront()
      } catch (error) {
        console.error('Error loading watershed outline:', error)
      }
    },

    handleOpacityChange(val) {
      if (this.snowLayer) {
        this.snowLayer.setOpacity(val / 100)
      }
    },

    async fetchLatestDate() {
      try {
        const res = await request.get('/raster-datasets/1/dates/')
        const dates = this.normalizeDateList(res)
        if (dates.length > 0) {
          // 取最大日期（最新）
          this.latestDate = [...dates].filter(Boolean).sort().pop()
        }
      } catch (e) {
        // 明确提示认证错误，方便排查
        const status = e?.response?.status
        const detail = e?.response?.data?.detail || ''
        if (status === 401) {
          this.$message.warning('数据日期接口需要登录认证，暂时显示本地数据日期')
          console.warn('[SnowRemote] /raster-datasets/1/dates/ 返回 401，detail:', detail)
        } else {
          this.$message.error('获取数据日期失败: ' + (e.message || '未知错误'))
          console.error('[SnowRemote] fetchLatestDate error:', e)
        }
        // fallback：从 HDF 文件名提取日期（MOD10A1.A2026005 → 2026-01-05）
        this.latestDate = this.parseHdfDate('A2026005')
      }
    },

    normalizeDateList(response) {
      const payload = response && response.data !== undefined ? response.data : response
      if (!payload) return []
      if (Array.isArray(payload)) return payload
      if (Array.isArray(payload.data)) return payload.data
      if (Array.isArray(payload.results)) return payload.results
      if (Array.isArray(payload.dates)) return payload.dates
      if (typeof payload === 'string') return [payload]
      return []
    },

    // 从 MODIS HDF 文件名中的儒略日解析为 YYYY-MM-DD
    parseHdfDate(julianTag) {
      // 例如 A2026005 → year=2026, doy=5
      const match = julianTag.match(/A(\d{4})(\d{3})/)
      if (!match) return ''
      const year = parseInt(match[1], 10)
      const doy = parseInt(match[2], 10)
      const date = new Date(year, 0, doy)
      const yyyy = date.getFullYear()
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      const dd = String(date.getDate()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd}`
    },

    async handleRefresh() {
      if (this.refreshLoading) return
      this.refreshLoading = true

      try {
        const { data } = await request.post('/raster-datasets/1/run/')
        const taskId = data.task_id
        this.$message.info('已开始更新，请稍候...')

        // 轮询任务状态（每 10 秒）
        this.pollTimer = setInterval(async() => {
          try {
            const { data: t } = await request.get(`/tasks/${taskId}/`)
            if (t.status === 'SUCCESS') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.refreshLoading = false
              this.$message.success('积雪数据已更新')
              // 刷新数据日期
              await this.fetchLatestDate()
              // 强制刷新瓦片（绕过浏览器缓存）
              if (this.snowLayer) {
                this.snowLayer.setUrl(`/api/tiles/modis-snow/{z}/{x}/{y}.png?v=${Date.now()}`)
              }
            } else if (t.status === 'FAILURE') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.refreshLoading = false
              this.$message.error('更新失败：' + (t.error || '未知错误'))
            }
            // PENDING / STARTED 继续轮询
          } catch (err) {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.refreshLoading = false
            this.$message.error('轮询任务状态失败')
            console.error(err)
          }
        }, 10000)
      } catch (e) {
        this.refreshLoading = false
        this.$message.error('触发更新失败')
        console.error(e)
      }
    }
  }
}
</script>

<style scoped>
.whiterisk-theme {
  background-color: #f8f9fa;
  color: #1e2125;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
  padding-bottom: 50px;
  min-height: 100%;
}

.page-header {
  padding: 32px 5%;
  background: white;
  border-bottom: 1px solid #eaedf2;
}

.page-header h1 {
  font-size: 26px;
  margin: 0;
  font-weight: 600;
  color: #0f172a;
}

.page-desc {
  font-size: 14px;
  color: #64748b;
  margin: 8px 0 0 0;
}

.breadcrumb {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.dashboard-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 20px;
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border: 1px solid #eaedf2;
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: transform 0.2s, box-shadow 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

/* 主地图展示 */
.main-visual {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
}

.visual-card {
  background: white;
  border: 1px solid #eaedf2;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #eaedf2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  font-size: 11px;
  padding: 3px 10px;
  background: #f1f5f9;
  color: #475569;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

/* 地图容器 */
.map-container-wrapper {
  position: relative;
  width: 100%;
  height: 600px;
}

.snow-map {
  width: 100%;
  height: 100%;
  background: #e8e8e8;
}

/* 地图图例 */
.map-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 12px 14px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
  z-index: 500;
  min-width: 140px;
}

.legend-title {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.map-legend .legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
  font-size: 11px;
  color: #334155;
}

.legend-swatch {
  width: 18px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.legend-range {
  font-size: 11px;
}

.legend-note {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
}

/* 透明度控制 */
.map-opacity-control {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 12px 14px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
  z-index: 500;
  width: 160px;
}

.opacity-label {
  font-size: 11px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 6px;
}

.opacity-value {
  font-size: 11px;
  color: #64748b;
  text-align: right;
  margin-top: 2px;
}

/* 侧边面板 */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-card {
  background: white;
  border: 1px solid #eaedf2;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.info-card h4 {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 12px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #f1f5f9;
}

/* 图例 */
.legend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.side-panel .legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.legend-color {
  width: 20px;
  height: 14px;
  border-radius: 3px;
  flex-shrink: 0;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.legend-label {
  font-weight: 500;
  color: #334155;
  min-width: 70px;
}

.legend-desc {
  color: #94a3b8;
  font-size: 11px;
}

/* 空间范围 */
.range-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.range-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.range-key {
  color: #64748b;
}

.range-val {
  color: #0f172a;
  font-weight: 500;
}

/* 数据状态 */
.data-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.status-key {
  color: #64748b;
}

.status-val {
  color: #0f172a;
  font-weight: 500;
}

/* 数据说明 */
.data-notes {
  margin: 0;
  padding-left: 16px;
  font-size: 12px;
  color: #475569;
  line-height: 1.8;
}

.data-notes li {
  margin-bottom: 4px;
}

/* 响应式 */
@media (max-width: 1024px) {
  .main-visual {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .map-container-wrapper {
    height: 450px;
  }
}

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: 1fr;
  }

  .page-header {
    padding: 20px 16px;
  }

  .dashboard-content {
    padding: 16px;
  }

  .map-container-wrapper {
    height: 350px;
  }

  .map-legend,
  .map-opacity-control {
    padding: 8px 10px;
  }

  .map-opacity-control {
    width: 130px;
  }
}
</style>
