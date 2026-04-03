import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  Image, 
  ScrollView, 
  TextInput,
  Alert,
  SafeAreaView,
  Platform
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import * as Location from 'expo-location';
import Toast from 'react-native-toast-message';
import { diagnoseCrop } from '../api/diagnose';
import LoadingOverlay from '../components/LoadingOverlay';
import { theme } from '../theme';

const DiagnoseScreen = ({ navigation }) => {
  const [image, setImage] = useState(null);
  const [cropType, setCropType] = useState('');
  const [gpsData, setGpsData] = useState(null);
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
        allowsEditing: false,
        quality: 1,
      });
    } else {
      result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: false,
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
    <SafeAreaView style={styles.safeArea}>
      <LoadingOverlay visible={loading} message="🔬 Analyzing crop..." />
      
      <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Headline Section */}
        <View style={styles.headerContainer}>
          <Text style={styles.headerTitle}>Diagnose Your Crop</Text>
          <Text style={styles.headerSubtitle}>Get instant insights about your crop health using AI-powered visual analysis.</Text>
        </View>

        {/* Tip Banner */}
        <View style={styles.tipBanner}>
          <MaterialIcons name="lightbulb" size={20} color={theme.colors.tertiary} />
          <Text style={styles.tipText}>Tip: For best results, photograph a single leaf in good lighting.</Text>
        </View>

        {/* Upload Zone & Preview */}
        {image ? (
          <View style={styles.previewContainer}>
            <Image source={{ uri: image }} style={styles.previewImage} />
            <TouchableOpacity style={styles.clearImageBtn} onPress={() => setImage(null)}>
              <MaterialIcons name="close" size={20} color={theme.colors.onError} />
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity style={styles.uploadZone} onPress={() => handleSelectImage('gallery')} activeOpacity={0.8}>
            <View style={styles.uploadIconWrapper}>
              <MaterialIcons name="energy-savings-leaf" size={32} color={theme.colors.primary} />
            </View>
            <Text style={styles.uploadText}>Tap to take photo or upload from gallery</Text>
          </TouchableOpacity>
        )}

        {/* Action Buttons */}
        {!image && (
          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.actionCard} onPress={() => handleSelectImage('camera')} activeOpacity={0.7}>
              <MaterialIcons name="photo-camera" size={28} color={theme.colors.primary} />
              <Text style={styles.actionCardText}>Take Photo</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.actionCard} onPress={() => handleSelectImage('gallery')} activeOpacity={0.7}>
              <MaterialIcons name="image" size={28} color={theme.colors.primary} />
              <Text style={styles.actionCardText}>From Gallery</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Details Card */}
        <View style={styles.detailsSection}>
          <View style={styles.detailsCard}>
            
            {/* Crop Type Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>CROP TYPE</Text>
              <TextInput 
                style={styles.input} 
                placeholder="e.g. Tomato, Wheat" 
                placeholderTextColor={theme.colors.outline}
                value={cropType}
                onChangeText={setCropType}
              />
            </View>

            <View style={styles.divider} />

            {/* GPS Location Section */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>LOCATION INTELLIGENCE</Text>
              <View style={styles.gpsContainer}>
                <View style={styles.gpsLeft}>
                  <MaterialIcons name="location-on" size={24} color={theme.colors.onSurfaceVariant} />
                  <View>
                    <Text style={styles.gpsTitle}>GPS Coordinates</Text>
                    <Text style={styles.gpsValues}>
                      Lat: {gpsData ? gpsData.lat : '—'}   Lon: {gpsData ? gpsData.lon : '—'}
                    </Text>
                  </View>
                </View>
                <TouchableOpacity style={styles.detectBtn} onPress={handleGetLocation}>
                  <Text style={styles.detectBtnText}>Detect Location</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </View>

        {error && <Text style={styles.errorText}>{error}</Text>}

        {/* Primary Action Button */}
        <TouchableOpacity 
          style={[styles.analyzeButton, !image && styles.analyzeButtonDisabled]} 
          onPress={handleSubmit}
          disabled={!image || loading}
          activeOpacity={0.9}
        >
          <Text style={styles.analyzeButtonText}>Analyze Crop</Text>
        </TouchableOpacity>

        {/* Bottom padding for tab bar */}
        <View style={{height: 100}} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.background,
    paddingTop: Platform.OS === 'android' ? 40 : 0,
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 16,
    gap: 24,
  },
  headerContainer: {
    gap: 8,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: 16,
    color: theme.colors.onSurfaceVariant,
    lineHeight: 24,
  },
  tipBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: theme.colors.tertiaryFixed,
    padding: 20,
    borderRadius: 12,
    gap: 16,
    borderWidth: 1,
    borderColor: 'rgba(255, 185, 87, 0.2)',
  },
  tipText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '500',
    color: theme.colors.onTertiaryFixed,
    lineHeight: 20,
  },
  uploadZone: {
    height: 180,
    borderWidth: 2,
    borderColor: 'rgba(13, 99, 27, 0.3)',
    borderStyle: 'dashed',
    backgroundColor: 'rgba(46, 125, 50, 0.05)',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  uploadIconWrapper: {
    width: 56,
    height: 56,
    backgroundColor: 'rgba(46, 125, 50, 0.1)',
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  uploadText: {
    color: theme.colors.primary,
    fontWeight: '600',
    fontSize: 14,
    paddingHorizontal: 32,
    textAlign: 'center',
  },
  previewContainer: {
    height: 300,
    width: '100%',
    borderRadius: 16,
    overflow: 'hidden',
    position: 'relative',
  },
  previewImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  clearImageBtn: {
    position: 'absolute',
    top: 12,
    right: 12,
    backgroundColor: theme.colors.error,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 16,
  },
  actionCard: {
    flex: 1,
    backgroundColor: theme.colors.surfaceContainerLowest,
    padding: 24,
    borderRadius: 16,
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: 'rgba(191, 202, 186, 0.1)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  actionCardText: {
    fontWeight: '700',
    fontSize: 14,
    color: theme.colors.onSurface,
  },
  detailsSection: {
    backgroundColor: theme.colors.surfaceContainerLow,
    borderRadius: 16,
    padding: 4,
  },
  detailsCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    padding: 24,
    gap: 24,
  },
  inputGroup: {
    gap: 8,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    ...theme.typography.label,
  },
  input: {
    backgroundColor: theme.colors.surfaceContainerHighest,
    padding: 16,
    borderRadius: 8,
    color: theme.colors.onSurface,
    fontSize: 16,
  },
  divider: {
    height: 1,
    backgroundColor: theme.colors.surfaceContainer,
  },
  gpsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  gpsLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  gpsTitle: {
    fontSize: 12,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
  },
  gpsValues: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.onSurface,
    marginTop: 2,
  },
  detectBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: theme.colors.primary,
    borderRadius: 999,
  },
  detectBtnText: {
    color: theme.colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  analyzeButton: {
    backgroundColor: theme.colors.primary,
    paddingVertical: 20,
    borderRadius: 999,
    alignItems: 'center',
    shadowColor: theme.colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 4,
    marginTop: 16,
  },
  analyzeButtonDisabled: {
    backgroundColor: theme.colors.outline,
    shadowOpacity: 0,
    elevation: 0,
  },
  analyzeButtonText: {
    color: theme.colors.onPrimary,
    fontSize: 18,
    fontWeight: '700',
  },
  errorText: { 
    color: theme.colors.error, 
    fontWeight: '600', 
    textAlign: 'center' 
  },
});

export default DiagnoseScreen;
