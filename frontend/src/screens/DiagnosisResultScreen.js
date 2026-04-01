import React, { useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  Image, 
  ScrollView, 
  TouchableOpacity, 
  Share,
  Dimensions
} from 'react-native';
import SeverityBadge from '../components/SeverityBadge';
import { saveLastDiagnosis } from '../utils/storage';

const { width } = Dimensions.get('window');

const DiagnosisResultScreen = ({ route, navigation }) => {
  const { result } = route.params;
  const { status, detections, annotated_image } = result;

  const isHealthy = status === 'healthy' || (detections && detections.length === 0);

  useEffect(() => {
    if (!isHealthy && detections.length > 0) {
      const top = detections[0];
      saveLastDiagnosis({
        disease_name: top.disease,
        confidence: top.confidence,
        severity: top.severity,
        date: new Date().toISOString(),
      });
    } else if (isHealthy) {
      saveLastDiagnosis({
        disease_name: 'Healthy',
        confidence: 1.0,
        severity: 'Mild',
        date: new Date().toISOString(),
      });
    }
  }, []);

  const handleShare = async () => {
    try {
      await Share.share({
        message: `KrishiMitra Diagnosis: ${isHealthy ? 'Healthy crop' : detections[0].disease}. Check out the annotated image.`,
        url: `data:image/jpeg;base64,${annotated_image}`, // Note: Base64 sharing support varies by platform
      });
    } catch (error) {
      console.log(error.message);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
        <Text style={styles.backButtonText}>← New Diagnosis</Text>
      </TouchableOpacity>

      <View style={styles.imageCard}>
        <Image 
          source={{ uri: `data:image/jpeg;base64,${annotated_image}` }} 
          style={styles.annotatedImage}
          resizeMode="cover"
        />
      </View>

      {isHealthy ? (
        <View style={[styles.card, styles.healthyCard]}>
          <Text style={styles.healthyText}>✅ Your crop looks healthy! No disease detected.</Text>
        </View>
      ) : (
        <View>
          <Text style={styles.resultTitle}>Detections:</Text>
          {detections.map((det, index) => (
            <View key={index} style={styles.diseaseCard}>
              <View style={styles.diseaseHeader}>
                <Text style={styles.diseaseName}>{det.disease}</Text>
                <SeverityBadge severity={det.severity} />
              </View>
              
              <Text style={styles.confidenceLabel}>Confidence: {(det.confidence * 100).toFixed(1)}%</Text>
              <View style={styles.progressContainer}>
                <View style={[styles.progressBar, { width: `${det.confidence * 100}%` }]} />
              </View>
            </View>
          ))}
        </View>
      )}

      <TouchableOpacity style={styles.shareButton} onPress={handleShare}>
        <Text style={styles.shareButtonText}>Share Result</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.resetButton} onPress={() => navigation.popToTop()}>
        <Text style={styles.resetButtonText}>Diagnose Another</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 20, paddingTop: 50 },
  backButton: { marginBottom: 20 },
  backButtonText: { color: '#2E7D32', fontSize: 16, fontWeight: 'bold' },
  imageCard: { 
    width: '100%', 
    height: 300, 
    borderRadius: 12, 
    overflow: 'hidden', 
    backgroundColor: '#000',
    marginBottom: 20,
    elevation: 3
  },
  annotatedImage: { width: '100%', height: '100%' },
  card: { padding: 20, borderRadius: 12, marginBottom: 20, elevation: 2 },
  healthyCard: { backgroundColor: '#E8F5E9', borderWidth: 1, borderColor: '#2E7D32' },
  healthyText: { color: '#2E7D32', fontSize: 16, fontWeight: 'bold', textAlign: 'center' },
  resultTitle: { fontSize: 18, fontWeight: 'bold', color: '#333', marginBottom: 15 },
  diseaseCard: { 
    backgroundColor: '#FFF', 
    padding: 16, 
    borderRadius: 12, 
    marginBottom: 16, 
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 3
  },
  diseaseHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  diseaseName: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  confidenceLabel: { fontSize: 14, color: '#666', marginBottom: 6 },
  progressContainer: { height: 8, backgroundColor: '#EEE', borderRadius: 4, overflow: 'hidden' },
  progressBar: { height: '100%', backgroundColor: '#2E7D32' },
  shareButton: { 
    backgroundColor: '#2E7D32', 
    height: 56, 
    borderRadius: 12, 
    justifyContent: 'center', 
    alignItems: 'center',
    marginTop: 20
  },
  shareButtonText: { color: '#FFF', fontSize: 16, fontWeight: 'bold' },
  resetButton: { 
    height: 56, 
    borderRadius: 12, 
    justifyContent: 'center', 
    alignItems: 'center',
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#CCC',
    marginBottom: 40
  },
  resetButtonText: { color: '#333', fontSize: 16, fontWeight: 'bold' }
});

export default DiagnosisResultScreen;
