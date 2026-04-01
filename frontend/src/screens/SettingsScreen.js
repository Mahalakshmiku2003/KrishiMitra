import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ScrollView, 
  Alert,
  ActivityIndicator
} from 'react-native';
import Toast from 'react-native-toast-message';
import { BASE_URL as DEFAULT_BASE_URL } from '../utils/config';
import { getCustomBaseUrl, saveCustomBaseUrl, clearAllData } from '../utils/storage';
import axios from 'axios';

const SettingsScreen = () => {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [isTesting, setIsTesting] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState(null);

  useEffect(() => {
    const loadUrl = async () => {
      const custom = await getCustomBaseUrl();
      if (custom) setBaseUrl(custom);
    };
    loadUrl();
  }, []);

  const handleSaveUrl = async () => {
    await saveCustomBaseUrl(baseUrl);
    Toast.show({ type: 'success', text1: 'Settings Saved', text2: 'Base URL updated successfully' });
  };

  const testConnection = async () => {
    setIsTesting(true);
    try {
      const res = await axios.get(`${baseUrl}/health`, { timeout: 5000 });
      if (res.status === 200) {
        Toast.show({ type: 'success', text1: 'Connection OK', text2: `KrishiMitra ${res.data.version || 'v1.0'}` });
      }
    } catch (err) {
      Toast.show({ type: 'error', text1: 'Connection Failed', text2: 'Is the server running?' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleFetchPrices = async () => {
    setIsFetching(true);
    setFetchStatus(null);
    try {
      const res = await axios.post(`${baseUrl}/market/fetch`, {}, { timeout: 60000 });
      if (res.status === 200) {
        setFetchStatus({ type: 'success', text: '✅ Prices updated successfully' });
        Toast.show({ type: 'success', text1: 'Update Complete', text2: 'Prices synchronized' });
      }
    } catch (err) {
      setFetchStatus({ type: 'error', text: '❌ Fetch failed. Try again.' });
      Toast.show({ type: 'error', text1: 'Update Failed', text2: 'Could not sync market data' });
    } finally {
      setIsFetching(false);
    }
  };

  const handleClearCache = () => {
    Alert.alert(
      "Clear Cached Data",
      "This will remove all local history and diagnosis. Are you sure?",
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Clear All", 
          style: "destructive", 
          onPress: async () => {
            await clearAllData();
            Toast.show({ type: 'success', text1: '🗑 Cache cleared', text2: 'All local data removed' });
          } 
        }
      ]
    );
  };

  const renderSectionHeader = (title) => (
    <Text style={styles.sectionHeader}>{title}</Text>
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Settings</Text>

      {renderSectionHeader('Connection')}
      <View style={styles.section}>
        <Text style={styles.label}>Backend Base URL</Text>
        <TextInput 
          style={styles.input} 
          value={baseUrl} 
          onChangeText={setBaseUrl}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <View style={styles.row}>
          <TouchableOpacity style={[styles.btn, styles.saveBtn]} onPress={handleSaveUrl}>
            <Text style={styles.btnText}>Save URL</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.testBtn]} onPress={testConnection} disabled={isTesting}>
            {isTesting ? <ActivityIndicator color="#2E7D32" size="small" /> : <Text style={[styles.btnText, { color: '#2E7D32' }]}>Test Health</Text>}
          </TouchableOpacity>
        </View>
      </View>

      {renderSectionHeader('Data')}
      <View style={styles.section}>
        <TouchableOpacity style={styles.listBtn} onPress={handleFetchPrices} disabled={isFetching}>
          {isFetching ? <ActivityIndicator color="#2E7D32" /> : <Text style={styles.listBtnText}>Fetch Latest Prices</Text>}
        </TouchableOpacity>
        {fetchStatus && (
          <Text style={[styles.statusText, { color: fetchStatus.type === 'success' ? '#2E7D32' : '#C62828' }]}>
            {fetchStatus.text}
          </Text>
        )}

        <TouchableOpacity style={[styles.listBtn, { borderBottomWidth: 0 }]} onPress={handleClearCache}>
          <Text style={[styles.listBtnText, { color: '#C62828' }]}>Clear Cached Data</Text>
        </TouchableOpacity>
      </View>

      {renderSectionHeader('About')}
      <View style={styles.section}>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>App Version</Text>
          <Text style={styles.infoValue}>1.0.0</Text>
        </View>
        <View style={[styles.infoRow, { borderBottomWidth: 0 }]}>
          <Text style={styles.infoLabel}>Build</Text>
          <Text style={styles.infoValue}>Production</Text>
        </View>
      </View>

      <Text style={styles.footerNote}>KrishiMitra v1.0 — Built for Indian Farmers</Text>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 24, paddingTop: 60 },
  header: { fontSize: 28, fontWeight: 'bold', color: '#2E7D32', marginBottom: 24 },
  sectionHeader: { fontSize: 14, fontWeight: 'bold', color: '#9E9E9E', textTransform: 'uppercase', marginBottom: 12, marginLeft: 4 },
  section: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, marginBottom: 24, elevation: 2 },
  label: { fontSize: 14, fontWeight: '500', color: '#333', marginBottom: 8 },
  input: { 
    height: 48, 
    backgroundColor: '#FAFAFA', 
    borderRadius: 8, 
    borderWidth: 1, 
    borderColor: '#EEE', 
    paddingHorizontal: 16, 
    marginBottom: 16,
    fontSize: 14,
    color: '#666'
  },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  btn: { flex: 0.48, height: 44, borderRadius: 8, justifyContent: 'center', alignItems: 'center' },
  saveBtn: { backgroundColor: '#2E7D32' },
  testBtn: { backgroundColor: '#F0F4F0', borderWidth: 1, borderColor: '#2E7D32' },
  btnText: { color: '#FFF', fontWeight: 'bold', fontSize: 14 },
  listBtn: { height: 56, justifyContent: 'center', borderBottomWidth: 1, borderBottomColor: '#F5F5F5' },
  listBtnText: { fontSize: 16, color: '#333' },
  statusText: { fontSize: 12, marginTop: 8, textAlign: 'center' },
  infoRow: { height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#F5F5F5' },
  infoLabel: { fontSize: 16, color: '#333' },
  infoValue: { fontSize: 16, color: '#9E9E9E' },
  footerNote: { textAlign: 'center', color: '#9E9E9E', fontSize: 13, marginTop: 10, marginBottom: 40 }
});

export default SettingsScreen;
