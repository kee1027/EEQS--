<template>
  <div class="whiterisk-theme">
    <header class="page-header">
      <nav class="breadcrumb">{{ REMOTE_PAGE_META.breadcrumb }}</nav>
      <h1>{{ REMOTE_PAGE_META.title }}</h1>
      <p class="page-desc">{{ REMOTE_PAGE_META.description }}</p>
    </header>

    <main class="dashboard-content">
      <!-- 图层切换 -->
      <div class="layer-switch" role="tablist" aria-label="遥感数据图层">
        <button
          v-for="layer in REMOTE_LAYERS"
          :key="layer.key"
          type="button"
          class="layer-tab"
          :class="{ active: layer.key === activeLayerKey }"
          :aria-selected="layer.key === activeLayerKey"
          role="tab"
          @click="handleLayerChange(layer.key)"
        >
          <span class="layer-tab-icon">{{ layer.icon }}</span>
          <span class="layer-tab-text">
            <strong>{{ layer.label }}</strong>
          </span>
        </button>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-row">
        <div v-for="stat in displayStats" :key="stat.label" class="stat-card">
          <div class="stat-icon" :style="{ background: stat.background, color: stat.color }">{{ stat.icon }}</div>
          <div class="stat-info">
            <div class="stat-value">{{ stat.displayValue }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>

      <!-- 主地图展示区 -->
      <div class="main-visual">
        <div class="visual-card">
          <div class="card-header">
            <h3>{{ activeLayer.mapTitle }}</h3>
            <div class="card-tags">
              <span v-for="tag in activeLayer.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>
          <div class="map-container-wrapper">
            <div id="snow-map-container" class="snow-map" />

            <!-- 图例 -->
            <div class="map-legend">
              <div class="legend-title">{{ activeLayer.legendTitle }}</div>
              <div v-for="item in activeLayer.legend" :key="item.label" class="legend-item">
                <span class="legend-swatch" :style="{ background: item.color }" />
                <span class="legend-range">{{ item.label }}</span>
              </div>
              <div class="legend-note">{{ activeLayer.legendNote }}</div>
            </div>

            <!-- 透明度控制 -->
            <div class="map-opacity-control">
              <div class="opacity-label">{{ activeLayer.label }}透明度</div>
              <el-slider
                v-model="activeOpacity"
                :min="0"
                :max="100"
                :show-tooltip="false"
                @input="handleOpacityChange"
              />
              <div class="opacity-value">{{ activeOpacity }}%</div>
            </div>
          </div>
        </div>

        <!-- 侧边信息面板 -->
        <div class="side-panel">
          <div class="info-card">
            <h4>{{ activeLayer.icon }} {{ activeLayer.label }}图例</h4>
            <div class="legend-list">
              <div v-for="item in activeLayer.legend" :key="item.label" class="legend-item">
                <span class="legend-color" :style="{ background: item.color }" />
                <span class="legend-label">{{ item.label }}</span>
                <span class="legend-desc">{{ item.description }}</span>
              </div>
            </div>
          </div>

          <div class="info-card">
            <h4>📍 空间范围</h4>
            <div class="range-info">
              <div v-for="row in activeLayer.rangeRows" :key="row.key" class="range-row">
                <span class="range-key">{{ row.key }}</span>
                <span class="range-val">{{ row.value }}</span>
              </div>
            </div>
          </div>

          <div class="info-card">
            <h4>📋 数据状态</h4>
            <div class="data-status">
              <div class="status-row">
                <span class="status-key">最新数据</span>
                <span class="status-val">{{ displayDate }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">更新方式</span>
                <span class="status-val">{{ activeLayer.updateMethod }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">瓦片缩放</span>
                <span class="status-val">{{ zoomRange }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">服务状态</span>
                <span class="status-val">{{ activeLayer.serviceStatus }}</span>
              </div>
            </div>
            <el-button
              v-if="activeLayer.refreshable"
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
              <li v-for="note in activeLayer.notes" :key="note">{{ note }}</li>
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
import { getRasterDates, getRasterTask, runRasterDataset } from '@/api/raster'
import { REMOTE_LAYERS, REMOTE_PAGE_META, SNOW_DATASET_ID } from './remote-layers'

proj4.defs('LCC', '+proj=lcc +lat_1=30 +lat_2=60 +lat_0=0 +lon_0=100 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')

// 阿勒泰区域常量
const ALTAY_BOUNDS = L.latLngBounds([[45.0, 85.5], [49.2, 91.1]])
const ALTAY_CENTER = [47.1, 88.3]
const TRANSPARENT_TILE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg=='

export default {
  name: 'SnowRemote',
  data() {
    const layerOpacities = {}
    REMOTE_LAYERS.forEach(layer => {
      layerOpacities[layer.key] = layer.defaultOpacity
    })

    return {
      map: null,
      rasterLayer: null,
      baseLayer: null,
      activeLayerKey: REMOTE_LAYERS[0].key,
      layerOpacities,
      latestDate: '',
      refreshLoading: false,
      pollTimer: null,
      REMOTE_PAGE_META,
      REMOTE_LAYERS
    }
  },
  computed: {
    activeLayer() {
      return this.REMOTE_LAYERS.find(layer => layer.key === this.activeLayerKey) || this.REMOTE_LAYERS[0]
    },
    activeOpacity: {
      get() {
        return this.layerOpacities[this.activeLayer.key]
      },
      set(value) {
        this.$set(this.layerOpacities, this.activeLayer.key, value)
      }
    },
    displayDate() {
      if (this.activeLayer.key === 'modis-snow') {
        return this.latestDate || '--'
      }
      const dateStat = this.activeLayer.stats.find(stat => stat.label === '数据日期')
      return dateStat ? dateStat.value : '--'
    },
    displayStats() {
      return this.activeLayer.stats.map(stat => ({
        ...stat,
        displayValue: stat.valueKey === 'latestDate' ? (this.latestDate || '--') : stat.value
      }))
    },
    zoomRange() {
      return `z${this.activeLayer.minZoom} ~ z${this.activeLayer.maxZoom}`
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
      this.pollTimer = null
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
        minZoom: 6,
        maxZoom: 14,
        zoomControl: true,
        attributionControl: false
      })

      // 底图（现有瓦片服务）
      this.baseLayer = L.tileLayer('/api/tiles/default/{z}/{x}/{y}.png', {
        minZoom: 7,
        maxZoom: 14,
        errorTileUrl: TRANSPARENT_TILE
      }).addTo(this.map)

      // 视野限制在数据区域附近
      const paddedBounds = ALTAY_BOUNDS.pad(0.5)
      this.map.setMaxBounds(paddedBounds)

      // 添加比例尺
      L.control.scale({ position: 'bottomright', metric: true, imperial: false }).addTo(this.map)

      // 流域轮廓固定置顶，随后挂载默认遥感图层
      this.loadWatershedOutline()
      this.renderActiveLayer()
    },

    renderActiveLayer() {
      if (!this.map || !this.activeLayer) return

      if (this.rasterLayer) {
        this.map.removeLayer(this.rasterLayer)
        this.rasterLayer = null
      }

      this.rasterLayer = L.tileLayer(this.activeLayer.tileUrl, {
        minZoom: this.activeLayer.minZoom,
        maxZoom: this.activeLayer.maxZoom,
        opacity: this.activeOpacity / 100,
        errorTileUrl: TRANSPARENT_TILE
      }).addTo(this.map)
    },

    handleLayerChange(layerKey) {
      if (this.activeLayerKey === layerKey) return
      this.activeLayerKey = layerKey
      this.renderActiveLayer()
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
      if (this.rasterLayer) {
        this.rasterLayer.setOpacity(val / 100)
      }
    },

    async fetchLatestDate() {
      try {
        const res = await getRasterDates(SNOW_DATASET_ID)
        const dates = this.normalizeDateList(res)
        if (dates.length > 0) {
          this.latestDate = [...dates].filter(Boolean).sort().pop()
        }
      } catch (e) {
        const status = e?.response?.status
        const detail = e?.response?.data?.detail || ''
        if (status === 401) {
          this.$message.warning('数据日期接口需要登录认证，暂时无法获取最新日期')
          console.warn('[SnowRemote] /raster-datasets/1/dates/ 返回 401，detail:', detail)
        } else {
          this.$message.error('获取数据日期失败: ' + (e.message || '未知错误'))
          console.error('[SnowRemote] fetchLatestDate error:', e)
        }
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

    async handleRefresh() {
      if (!this.activeLayer.refreshable || this.refreshLoading) return
      this.refreshLoading = true

      try {
        const { data } = await runRasterDataset(SNOW_DATASET_ID)
        const taskId = data.task_id
        this.$message.info('已开始更新，请稍候...')

        // 轮询任务状态（每 10 秒）
        this.pollTimer = setInterval(async() => {
          try {
            const { data: task } = await getRasterTask(taskId)
            if (task.status === 'SUCCESS') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.refreshLoading = false
              this.$message.success(`${this.activeLayer.label}数据已更新`)
              await this.fetchLatestDate()
              this.refreshRasterLayer(Date.now())
            } else if (task.status === 'FAILURE') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.refreshLoading = false
              this.$message.error('更新失败：' + (task.error || '未知错误'))
            }
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
    },

    refreshRasterLayer(version) {
      if (!this.rasterLayer || !this.activeLayer.refreshable) return
      this.rasterLayer.setUrl(`${this.activeLayer.tileUrl}?v=${version}`)
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

/* 图层切换 */
.layer-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.layer-tab {
  appearance: none;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.layer-tab:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
}

.layer-tab.active {
  border-color: #2c7be5;
  box-shadow: 0 0 0 2px rgba(44, 123, 229, 0.12);
}

.layer-tab-icon {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}

.layer-tab-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.layer-tab-text strong {
  font-size: 14px;
  color: #0f172a;
}

.layer-tab-text small {
  font-size: 11px;
  color: #94a3b8;
}

.layer-tab.active .layer-tab-text strong {
  color: #1d5fbf;
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
  .layer-switch {
    grid-template-columns: 1fr;
  }

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
