import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  Image, 
  ScrollView, 
  TextInput,
  Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import * as Location from 'expo-location';
import Toast from 'react-native-toast-message';
import { diagnoseCrop } from '../api/diagnose';
import LoadingOverlay from '../components/LoadingOverlay';

const DiagnoseScreen = ({ navigation }) => {
  const [image, setImage] = useState(null);
  const [cropType, setCropType] = useState('');
  const [gpsData, setGpsData] = useState(null);
  const [isOptionsVisible, setIsOptionsVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const requestPermissions = async () => {
    const { status: cam } = await ImagePicker.requestCameraPermissionsAsync();
    const { status: lib } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    const { status: loc } = await Location.requestForegroundPermissionsAsync();

    if (cam !== 'granted' || lib !== 'granted' || loc !== 'granted') {
      Alert.alert(
        'Permissions Required', 
        'KrishiMitra needs camera, gallery, and location access to diagnose your crops. Please check your settings.',
        [{ text: 'OK' }]
      );
      return false;
    }
    return true;
  };

  const handleSelectImage = async (mode) => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) return;

    let result;
    if (mode === 'camera') {
      result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        aspect: [4, 3],
        quality: 1,
      });
    } else {
      result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: true,
        aspect: [4, 3],
        quality: 1,
      });
    }

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setError(null);
    }
  };

  const handleGetLocation = async () => {
    try {
      const location = await Location.getCurrentPositionAsync({});
      setGpsData({
        lat: location.coords.latitude.toFixed(6),
        lon: location.coords.longitude.toFixed(6)
      });
    } catch (err) {
      Toast.show({ type: 'error', text1: 'Location Error', text2: 'Could not fetch GPS coordinates' });
    }
  };

  const handleSubmit = async () => {
    if (!image) return;

    setLoading(true);
    setError(null);

    try {
      const manipResult = await ImageManipulator.manipulateAsync(
        image,
        [{ resize: { width: 1024 } }],
        { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG }
      );

      const formData = new FormData();
      formData.append('file', {
        uri: manipResult.uri,
        name: 'crop.jpg',
        type: 'image/jpeg',
      });
      
      if (cropType) formData.append('crop_type', cropType);
      if (gpsData) {
        formData.append('gps_lat', gpsData.lat);
        formData.append('gps_lon', gpsData.lon);
      }

      const response = await diagnoseCrop(formData);
      
      Toast.show({ type: 'success', text1: '✅ Analysis complete', text2: 'Results retrieved successfully' });
      navigation.navigate('DiagnosisResult', { result: response.data });

    } catch (err) {
      console.error(err);
      let msg = "Analysis failed. Please try again.";
      if (err.code === 'ECONNABORTED') msg = "Server took too long. Is the backend running?";
      else if (err.response) msg = typeof err.response.data === 'string' ? err.response.data : "API Error";
      
      Toast.show({ type: 'error', text1: 'Diagnosis Failed', text2: msg });
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <LoadingOverlay visible={loading} message="🔬 Analyzing crop..." />
      
      <Text style={styles.header}>Diagnose Your Crop</Text>

      <View style={styles.sourceButtons}>
        <TouchableOpacity style={styles.sourceBtn} onPress={() => handleSelectImage('camera')}>
          <Ionicons name="camera" size={30} color="#2E7D32" />
          <Text style={styles.sourceText}>Take Photo</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.sourceBtn} onPress={() => handleSelectImage('gallery')}>
          <Ionicons name="image" size={30} color="#2E7D32" />
          <Text style={styles.sourceText}>From Gallery</Text>
        </TouchableOpacity>
      </View>

      {image && (
        <View style={styles.previewCard}>
          <Image source={{ uri: image }} style={styles.thumbnail} />
          <Text style={styles.imageSelectedText}>Image selected successfully</Text>
          <TouchableOpacity onPress={() => setImage(null)}>
            <Ionicons name="close-circle" size={24} color="#C62828" />
          </TouchableOpacity>
        </View>
      )}

      <TouchableOpacity 
        style={styles.collapsibleHeader} 
        onPress={() => setIsOptionsVisible(!isOptionsVisible)}
      >
        <Text style={styles.optionsTitle}>Optional Fields</Text>
        <Ionicons name={isOptionsVisible ? "chevron-up" : "chevron-down"} size={20} color="#666" />
      </TouchableOpacity>

      {isOptionsVisible && (
        <View style={styles.optionsContent}>
          <Text style={styles.label}>Crop Type</Text>
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Tomato, Wheat" 
            value={cropType}
            onChangeText={setCropType}
          />
          
          <View style={styles.gpsRow}>
            <View style={styles.gpsInfo}>
              <Text style={styles.label}>GPS Location</Text>
              <Text style={styles.gpsText}>Lat: {gpsData ? gpsData.lat : '--'}</Text>
              <Text style={styles.gpsText}>Lon: {gpsData ? gpsData.lon : '--'}</Text>
            </View>
            <TouchableOpacity style={styles.gpsButton} onPress={handleGetLocation}>
              <Text style={styles.gpsButtonText}>📍 Detect Location</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {error && <Text style={styles.errorText}>{error}</Text>}

      <TouchableOpacity 
        style={[styles.primaryButton, !image && styles.disabledButton]} 
        onPress={handleSubmit}
        disabled={!image || loading}
      >
        <Text style={styles.primaryButtonText}>Analyze Crop</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 24, paddingTop: 60 },
  header: { fontSize: 28, fontWeight: 'bold', color: '#2E7D32', marginBottom: 24 },
  sourceButtons: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 24 },
  sourceBtn: { 
    flex: 0.48, 
    backgroundColor: '#FFF', 
    padding: 16, 
    borderRadius: 12, 
    alignItems: 'center',
    elevation: 3,
    shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 4
  },
  sourceText: { marginTop: 8, color: '#2E7D32', fontWeight: 'bold' },
  previewCard: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    backgroundColor: '#E8F5E9', 
    padding: 12, 
    borderRadius: 12, 
    marginBottom: 24 
  },
  thumbnail: { width: 100, height: 100, borderRadius: 8 },
  imageSelectedText: { flex: 1, marginLeft: 12, color: '#2E7D32', fontWeight: '500' },
  collapsibleHeader: { 
    flexDirection: 'row', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    marginBottom: 16 
  },
  optionsTitle: { fontSize: 16, color: '#666', fontWeight: 'bold' },
  optionsContent: { backgroundColor: '#FFF', padding: 16, borderRadius: 12, marginBottom: 24 },
  label: { fontSize: 14, color: '#333', marginBottom: 8, fontWeight: '500' },
  input: { backgroundColor: '#F9F9F9', padding: 12, borderRadius: 8, marginBottom: 16, borderWidth: 1, borderColor: '#EEE' },
  gpsRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  gpsInfo: { flex: 1 },
  gpsText: { fontSize: 13, color: '#666' },
  gpsButton: { backgroundColor: '#F5F5F5', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#DDD' },
  gpsButtonText: { fontSize: 12, color: '#2E7D32', fontWeight: 'bold' },
  errorText: { color: '#C62828', marginBottom: 16, fontWeight: '500', textAlign: 'center' },
  primaryButton: { 
    backgroundColor: '#2E7D32', 
    height: 56, 
    borderRadius: 12, 
    justifyContent: 'center', 
    alignItems: 'center',
    elevation: 4
  },
  disabledButton: { backgroundColor: '#CCC' },
  primaryButtonText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' }
});

export default DiagnoseScreen;
