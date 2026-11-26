export const SNOW_DATASET_ID = 1

export const REMOTE_PAGE_META = {
  breadcrumb: '积雪动态 / 遥感',
  title: '积雪与雪崩风险遥感监测',
  description: '集成 MODIS 积雪覆盖与 SAFE 多源雪崩风险成果数据，支持图层切换和实时瓦片服务'
}

export const REMOTE_LAYERS = [
  {
    key: 'avalanche-risk',
    label: '雪崩风险',
    icon: '⚠️',
    availability: 'ready',
    mapTitle: '阿勒泰地区雪崩风险分布',
    tags: ['SAFE Risk Classes', 'EPSG:4326', '阈值 0.55 / 0.70 / 0.80'],
    stats: [
      { icon: '📅', label: '数据日期', value: '2023', background: '#e0f3f8', color: '#2c7fb8' },
      { icon: '🛰️', label: '数据产品', value: 'SAFE Multisource', background: '#fee090', color: '#d95f0e' },
      { icon: '📐', label: '空间分辨率', value: '20m', background: '#fdae61', color: '#a63603' },
      { icon: '🧪', label: '风险阈值', value: '0.55 / 0.70 / 0.80', background: '#f46d43', color: '#7f2704' }
    ],
    tileUrl: '/api/tiles/avalanche-risk/{z}/{x}/{y}.png',
    minZoom: 6,
    maxZoom: 14,
    defaultOpacity: 80,
    legendTitle: '雪崩风险等级',
    legend: [
      { color: '#fff7bc', label: '0.55 ~ 0.70', description: '较低风险' },
      { color: '#fb6a4a', label: '0.70 ~ 0.80', description: '较高风险' },
      { color: '#a50f15', label: '≥ 0.80', description: '高风险' }
    ],
    legendNote: '透明 = 无风险背景 / 无数据区',
    rangeRows: [
      { key: '经度', value: '85.5266°E ~ 91.0739°E' },
      { key: '纬度', value: '45.1919°N ~ 49.1831°N' },
      { key: '中心区域', value: '阿勒泰地区' }
    ],
    updateMethod: '2023 年静态成果数据',
    serviceStatus: '实时瓦片服务',
    refreshable: false,
    notes: [
      '数据来源为 SAFE Multisource 2023 雪崩风险分类成果',
      '采用 0.55、0.70、0.80 三个风险阈值进行分级',
      '原始栅格为 EPSG:4326、约 20 米分辨率单波段 GeoTIFF',
      '背景值 0 渲染为透明',
      '空间范围与当前阿勒泰流域边界基本一致'
    ]
  },
  {
    key: 'avalanche-confidence',
    label: '雪崩置信度',
    icon: '🧭',
    availability: 'ready',
    mapTitle: '阿勒泰地区雪崩风险置信度分布',
    tags: ['SAFE Confidence', 'EPSG:4326', '有效值约 0.71 ~ 1.00'],
    stats: [
      { icon: '📅', label: '数据日期', value: '2023', background: '#e0f3f8', color: '#2c7fb8' },
      { icon: '🛰️', label: '数据产品', value: 'SAFE Confidence', background: '#dbe9f6', color: '#225ea8' },
      { icon: '📐', label: '空间分辨率', value: '20m', background: '#74add1', color: '#08306b' },
      { icon: '✅', label: '有效范围', value: '风险分类区域', background: '#c6dbef', color: '#08519c' }
    ],
    tileUrl: '/api/tiles/avalanche-confidence/{z}/{x}/{y}.png',
    minZoom: 6,
    maxZoom: 14,
    defaultOpacity: 80,
    legendTitle: '雪崩风险置信度',
    legend: [
      { color: '#dbe9f6', label: '0.70 ~ 0.80', description: '较低置信度' },
      { color: '#73b3d8', label: '0.80 ~ 0.90', description: '中等置信度' },
      { color: '#2389bd', label: '0.90 ~ 0.95', description: '较高置信度' },
      { color: '#08306b', label: '0.95 ~ 1.00', description: '高置信度' }
    ],
    legendNote: '透明 = 无风险像元 / 无数据区',
    rangeRows: [
      { key: '经度', value: '85.5266°E ~ 91.0739°E' },
      { key: '纬度', value: '45.1919°N ~ 49.1831°N' },
      { key: '中心区域', value: '阿勒泰地区' }
    ],
    updateMethod: '2023 年静态成果数据',
    serviceStatus: '实时瓦片服务',
    refreshable: false,
    notes: [
      '该图层与雪崩风险分类图具有相同空间范围',
      '置信度为浮点型栅格，当前有效值约 0.71 ~ 1.00',
      '有效像元主要对应风险分类图中的非背景区域',
      '原始栅格为 EPSG:4326、约 20 米分辨率单波段 GeoTIFF',
      '背景区域渲染为透明'
    ]
  },
  {
    key: 'modis-snow',
    label: '积雪覆盖',
    icon: '❄️',
    availability: 'ready',
    mapTitle: '阿勒泰地区积雪覆盖分布',
    tags: ['NDSI Snow Cover', 'EPSG:4326', 'MOD10A1'],
    stats: [
      { icon: '📅', label: '数据日期', value: '--', valueKey: 'latestDate', background: '#e0f3f8', color: '#2c7fb8' },
      { icon: '🛰️', label: '数据产品', value: 'MOD10A1', background: '#fee090', color: '#d95f0e' },
      { icon: '📐', label: '空间分辨率', value: '500m', background: '#fdae61', color: '#a63603' },
      { icon: '🗺️', label: '覆盖瓦片', value: 'h23v04+h24v04', background: '#f46d43', color: '#7f2704' }
    ],
    tileUrl: '/api/tiles/modis-snow/{z}/{x}/{y}.png',
    minZoom: 6,
    maxZoom: 11,
    defaultOpacity: 80,
    legendTitle: '积雪覆盖率 (NDSI)',
    legend: [
      { color: '#e0f3f8', label: '0% ~ 20%', description: '无积雪/微量' },
      { color: '#74add1', label: '20% ~ 40%', description: '低覆盖' },
      { color: '#fee090', label: '40% ~ 60%', description: '中低覆盖' },
      { color: '#fdae61', label: '60% ~ 80%', description: '中高覆盖' },
      { color: '#f46d43', label: '80% ~ 100%', description: '高覆盖' }
    ],
    legendNote: '透明 = 无数据 / 云 / 水体',
    rangeRows: [
      { key: '经度', value: '85.5°E ~ 91.1°E' },
      { key: '纬度', value: '45.0°N ~ 49.2°N' },
      { key: '中心区域', value: '阿勒泰地区' }
    ],
    updateMethod: '每日 02:20 自动追新',
    serviceStatus: '实时瓦片服务',
    refreshable: true,
    notes: [
      '数据来源于 MODIS Terra 卫星 MOD10A1 产品',
      '采用 NDSI（归一化差分积雪指数）算法反演',
      '已过滤云和水体掩膜（无效值已剔除）',
      '两景影像（h23v04 + h24v04）无缝拼接',
      '从正弦投影重投影至 WGS84 坐标系'
    ]
  }
]
