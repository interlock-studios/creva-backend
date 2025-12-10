// Smart client-side region selection
const REGIONAL_ENDPOINTS = {
  'us-central1': 'https://zest-parser-g4zcestszq-uc.a.run.app',
  'us-east1': 'https://zest-parser-g4zcestszq-ue.a.run.app',
  'europe-west1': 'https://zest-parser-g4zcestszq-ew.a.run.app',
  'asia-southeast1': 'https://zest-parser-g4zcestszq-as.a.run.app'
};

function getOptimalEndpoint() {
  // Get user's timezone to determine region
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  
  if (timezone.includes('America')) {
    return Math.random() > 0.5 ? REGIONAL_ENDPOINTS['us-central1'] : REGIONAL_ENDPOINTS['us-east1'];
  } else if (timezone.includes('Europe') || timezone.includes('Africa')) {
    return REGIONAL_ENDPOINTS['europe-west1'];
  } else if (timezone.includes('Asia') || timezone.includes('Pacific')) {
    return REGIONAL_ENDPOINTS['asia-southeast1'];
  }
  
  // Default to us-central1
  return REGIONAL_ENDPOINTS['us-central1'];
}

// Usage in your frontend
const apiEndpoint = getOptimalEndpoint();
console.log('Using endpoint:', apiEndpoint);
    