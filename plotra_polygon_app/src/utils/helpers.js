/**
 * Async error wrapper - catches async function errors and rethrows as regular error
 */
export function catchAsync(fn) {
  return function (...args) {
    return fn.apply(this, args).catch((error) => {
      console.error('Async error in', fn.name, ':', error);
      throw error;
    });
  };
}

/**
 * Format date for display
 */
export function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-KE', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format area in hectares
 */
export function formatArea(hectares) {
  if (hectares < 0.01) return '< 0.01 ha';
  if (hectares < 1) return hectares.toFixed(3) + ' ha';
  return hectares.toFixed(2) + ' ha';
}

/**
 * Calculate distance between two coordinates in meters (Haversine)
 */
export function calculateDistance(coord1, coord2) {
  const R = 6371000; // Earth radius in meters
  const φ1 = (coord1.latitude * Math.PI) / 180;
  const φ2 = (coord2.latitude * Math.PI) / 180;
  const Δφ = ((coord2.latitude - coord1.latitude) * Math.PI) / 180;
  const Δλ = ((coord2.longitude - coord1.longitude) * Math.PI) / 180;

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) *
    Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

/**
 * Debounce function
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
