import AsyncStorage from '@react-native-async-storage/async-storage';

export const saveLastDiagnosis = async (data) => {
  try {
    const jsonValue = JSON.stringify(data);
    await AsyncStorage.setItem('last_diagnosis', jsonValue);
  } catch (e) {
    console.error("Error saving diagnosis", e);
  }
};

export const getLastDiagnosis = async () => {
  try {
    const jsonValue = await AsyncStorage.getItem('last_diagnosis');
    return jsonValue != null ? JSON.parse(jsonValue) : null;
  } catch (e) {
    console.error("Error reading diagnosis", e);
    return null;
  }
};

export const clearAllData = async () => {
  try {
    await AsyncStorage.clear();
  } catch(e) {
    console.error("Error clearing data", e);
  }
};

export const saveCustomBaseUrl = async (url) => {
  try {
    await AsyncStorage.setItem('custom_base_url', url);
  } catch (e) {
    console.error("Error saving base url", e);
  }
};

export const getCustomBaseUrl = async () => {
  try {
    return await AsyncStorage.getItem('custom_base_url');
  } catch (e) {
    return null;
  }
};

export const saveAssistantChat = async (messages) => {
  try {
    const jsonValue = JSON.stringify(messages.slice(-50)); // Keep last 50
    await AsyncStorage.setItem('assistant_chat', jsonValue);
  } catch (e) {
    console.error("Error saving chat", e);
  }
};

export const getAssistantChat = async () => {
  try {
    const jsonValue = await AsyncStorage.getItem('assistant_chat');
    return jsonValue != null ? JSON.parse(jsonValue) : [];
  } catch (e) {
    console.error("Error reading chat", e);
    return [];
  }
};
