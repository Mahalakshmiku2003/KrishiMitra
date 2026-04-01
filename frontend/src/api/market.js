import axios from 'axios';
import { BASE_URL as DEFAULT_BASE_URL } from '../utils/config';
import { getCustomBaseUrl } from '../utils/storage';

// Helper to get active base URL
const getActiveUrl = async () => {
  const custom = await getCustomBaseUrl();
  return custom || DEFAULT_BASE_URL;
};

export const getMarketPrices = async (commodity, state = '') => {
  const url = await getActiveUrl();
  return axios.get(`${url}/market/prices`, {
    params: { commodity, ...(state && { state }) }
  });
};

export const getNearbyMandis = async (location, commodity, radius_km = 100) => {
  const url = await getActiveUrl();
  return axios.post(`${url}/market/nearby`, { location, commodity, radius_km },
    { headers: { 'Content-Type': 'application/json' } });
};

export const getPricePrediction = async (commodity, market) => {
  const url = await getActiveUrl();
  return axios.get(`${url}/market/predict`, { params: { commodity, market } });
};

export const triggerPriceFetch = async () => {
  const url = await getActiveUrl();
  return axios.post(`${url}/market/fetch`);
};
