import request from '@/utils/request'

export function getRasterDates(datasetId) {
  return request.get(`/raster-datasets/${datasetId}/dates/`)
}

export function runRasterDataset(datasetId) {
  return request.post(`/raster-datasets/${datasetId}/run/`)
}

export function getRasterTask(taskId) {
  return request.get(`/tasks/${taskId}/`)
}
