import axios from 'axios';
import { BASE_URL } from '../utils/config';

export const diagnoseCrop = (formData) =>
  axios.post(`${BASE_URL}/diagnose`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000, // 30 seconds
  });
