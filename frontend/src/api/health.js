import axios from 'axios';
import { BASE_URL } from '../utils/config';

export const checkHealth = () => axios.get(`${BASE_URL}/health`);
