import axios from 'axios';
import { BASE_URL as DEFAULT_BASE_URL } from '../utils/config';
import { getCustomBaseUrl } from '../utils/storage';

// Helper to get active base URL
const getActiveUrl = async () => {
  const custom = await getCustomBaseUrl();
  return custom || DEFAULT_BASE_URL;
};

export const chatWithAssistant = async (message, farmerId = 'demo_farmer', imageUri = null) => {
  const url = await getActiveUrl();
  
  const formData = new FormData();
  formData.append('message', message);
  formData.append('farmer_id', farmerId);
  
  if (imageUri) {
    const filename = imageUri.split('/').pop();
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : `image`;
    
    formData.append('image', {
      uri: imageUri,
      name: filename,
      type: type,
    });
  }

  return axios.post(`${url}/assistant/chat`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

