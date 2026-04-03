import React, { useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  Image, 
  ScrollView, 
  TouchableOpacity, 
  Share,
  SafeAreaView,
  Platform
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { saveLastDiagnosis } from '../utils/storage';
import { theme } from '../theme';

const DiagnosisResultScreen = ({ route, navigation }) => {
  const { result } = route.params;
  const { status, detections, annotated_image } = result;

  const isHealthy = status === 'healthy' || (detections && detections.length === 0);

  useEffect(() => {
    if (!isHealthy && detections.length > 0) {
      const top = detections[0];
      saveLastDiagnosis({
        image_uri: `data:image/jpeg;base64,${annotated_image}`,
        disease_name: top.disease,
        confidence: top.confidence,
        severity: top.severity,
        date: new Date().toISOString(),
      });
    } else if (isHealthy) {
      saveLastDiagnosis({
        image_uri: `data:image/jpeg;base64,${annotated_image}`,
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
    <SafeAreaView style={styles.safeArea}>
      {/* TopAppBar */}
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backButton} 
          onPress={() => navigation.goBack()}
          activeOpacity={0.8}
        >
          <MaterialIcons name="arrow-back" size={24} color={theme.colors.primary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Diagnosis Result</Text>
      </View>

      <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        
        {/* Annotated Image Section */}
        <View style={styles.imageContainer}>
          <Image 
            source={{ uri: `data:image/jpeg;base64,${annotated_image}` }} 
            style={styles.annotatedImage}
            resizeMode="cover"
          />
        </View>

        {isHealthy ? (
          <View style={styles.healthyBanner}>
            <MaterialIcons name="check-circle" size={20} color="#FFFFFF" />
            <Text style={styles.bannerText}>Your crop looks healthy!</Text>
          </View>
        ) : (
          <View style={styles.warningBanner}>
            <MaterialIcons name="warning" size={20} color="#FFFFFF" />
            <Text style={styles.bannerText}>Disease Detected</Text>
          </View>
        )}

        {/* Results Cards */}
        {isHealthy ? (
          <View style={styles.resultCard}>
            <View style={styles.resultHeaderRow}>
              <View>
                <Text style={styles.identificationLabel}>IDENTIFICATION</Text>
                <Text style={styles.diseaseTitle}>Healthy Crop</Text>
              </View>
              <View style={[styles.stableBadge, { backgroundColor: theme.colors.primaryContainer }]}>
                <Text style={styles.stableBadgeText}>STABLE</Text>
              </View>
            </View>
          </View>
        ) : (
          detections.map((det, index) => (
            <View key={index} style={styles.resultSection}>
              {/* Main Result Card */}
              <View style={styles.resultCard}>
                <View style={styles.resultHeaderRow}>
                  <View>
                    <Text style={styles.identificationLabel}>IDENTIFICATION</Text>
                    <Text style={styles.diseaseTitle}>{det.disease}</Text>
                  </View>
                  <View style={[styles.stableBadge, { backgroundColor: det.severity === 'High' ? theme.colors.errorContainer : theme.colors.primaryContainer }]}>
                    <Text style={[styles.stableBadgeText, { color: det.severity === 'High' ? theme.colors.onErrorContainer : theme.colors.onPrimaryContainer }]}>
                      {det.severity === 'High' ? 'CRITICAL' : 'DETECTED'}
                    </Text>
                  </View>
                </View>

                <View style={styles.confidenceSection}>
                  <View style={styles.confidenceRow}>
                    <Text style={styles.confidenceLabel}>Confidence</Text>
                    <Text style={styles.confidenceValue}>{(det.confidence * 100).toFixed(0)}%</Text>
                  </View>
                  <View style={styles.progressBarTrack}>
                    <View style={[styles.progressBarFill, { width: `${det.confidence * 100}%` }]} />
                  </View>
                </View>

                <View style={styles.severityRow}>
                  <Text style={styles.severityLabel}>Severity</Text>
                  <View style={[
                      styles.severityBadge, 
                      { backgroundColor: det.severity === 'High' ? theme.colors.errorContainer : theme.colors.tertiaryFixed }
                  ]}>
                    <Text style={[
                        styles.severityBadgeText,
                        { color: det.severity === 'High' ? theme.colors.onErrorContainer : theme.colors.onTertiaryFixedVariant }
                    ]}>
                        {det.severity}
                    </Text>
                  </View>
                </View>

                <View style={styles.divider} />
                
                <View style={styles.outlookRow}>
                  <MaterialIcons name="calendar-today" size={20} color={theme.colors.onSurfaceVariant} />
                  <View style={styles.outlookTextGroup}>
                    <Text style={styles.outlookTitle}>7-Day Outlook</Text>
                    <Text style={styles.outlookSubtitle}>Condition may worsen if untreated. High humidity will accelerate fungal spread.</Text>
                  </View>
                </View>
              </View>

              {/* Treatment Card */}
              <View style={styles.treatmentCard}>
                <View style={styles.treatmentHeader}>
                  <MaterialIcons name="science" size={20} color={theme.colors.primary} />
                  <Text style={styles.treatmentTitle}>Recommended Action</Text>
                </View>
                <View style={styles.treatmentList}>
                  <View style={styles.treatmentListItem}>
                    <View style={styles.bulletPoint} />
                    <Text style={styles.treatmentItemText}>Consult a local agriculturist for precise <Text style={{fontWeight: '700', color: theme.colors.primary}}>fungicide</Text> instructions.</Text>
                  </View>
                  <View style={styles.treatmentListItem}>
                    <View style={styles.bulletPoint} />
                    <Text style={styles.treatmentItemText}>Remove and burn infected leaves immediately to stop spread.</Text>
                  </View>
                </View>
              </View>
            </View>
          ))
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtonsRow}>
          <TouchableOpacity 
            style={styles.btnSecondary} 
            onPress={() => navigation.popToTop()}
            activeOpacity={0.8}
          >
            <MaterialIcons name="refresh" size={20} color={theme.colors.primary} />
            <Text style={styles.btnSecondaryText}>Diagnose Another</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.btnPrimary} 
            onPress={handleShare}
            activeOpacity={0.8}
          >
            <MaterialIcons name="share" size={20} color={theme.colors.onPrimary} />
            <Text style={styles.btnPrimaryText}>Share Result</Text>
          </TouchableOpacity>
        </View>

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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: theme.colors.surfaceContainerLowest,
    zIndex: 10,
  },
  backButton: {
    padding: 8,
    marginLeft: -8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: theme.colors.primary,
    letterSpacing: -0.5,
    marginLeft: 8,
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    gap: 24,
  },
  imageContainer: {
    height: 240,
    width: '100%',
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: theme.colors.surfaceContainer,
  },
  annotatedImage: {
    width: '100%',
    height: '100%',
  },
  healthyBanner: {
    backgroundColor: theme.colors.primaryContainer,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
  },
  warningBanner: {
    backgroundColor: '#1B5E20',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
  },
  bannerText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  resultSection: {
    gap: 24,
  },
  resultCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 20,
    padding: 24,
    gap: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 20,
    elevation: 2,
  },
  resultHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  identificationLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    letterSpacing: 1,
    ...theme.typography.label,
  },
  diseaseTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: theme.colors.primary,
    marginTop: 4,
  },
  stableBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 999,
  },
  stableBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onPrimaryContainer,
    letterSpacing: 1,
  },
  confidenceSection: {
    gap: 8,
  },
  confidenceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  confidenceLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
  },
  confidenceValue: {
    fontSize: 20,
    fontWeight: '800',
    color: theme.colors.primary,
  },
  progressBarTrack: {
    height: 6,
    backgroundColor: theme.colors.surfaceContainer,
    borderRadius: 999,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
  },
  severityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  severityLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
  },
  severityBadge: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 999,
  },
  severityBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  divider: {
    height: 1,
    backgroundColor: theme.colors.surfaceContainerHigh,
    width: '100%',
  },
  outlookRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  outlookTextGroup: {
    flex: 1,
    gap: 4,
  },
  outlookTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: theme.colors.onSurface,
  },
  outlookSubtitle: {
    fontSize: 12,
    color: theme.colors.onSurfaceVariant,
    lineHeight: 18,
  },
  treatmentCard: {
    backgroundColor: '#e8f5e9',
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: '#c8e6c9',
  },
  treatmentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  treatmentTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  treatmentList: {
    gap: 12,
  },
  treatmentListItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  bulletPoint: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: theme.colors.primary,
    marginTop: 6,
  },
  treatmentItemText: {
    fontSize: 14,
    color: theme.colors.onSurfaceVariant,
    lineHeight: 20,
    flex: 1,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 8,
  },
  btnSecondary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    paddingHorizontal: 8,
    borderWidth: 2,
    borderColor: theme.colors.primary,
    borderRadius: 16,
  },
  btnSecondaryText: {
    color: theme.colors.primary,
    fontWeight: '700',
    fontSize: 14,
  },
  btnPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    paddingHorizontal: 8,
    backgroundColor: theme.colors.primaryContainer,
    borderRadius: 16,
    shadowColor: theme.colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 4,
  },
  btnPrimaryText: {
    color: theme.colors.onPrimaryContainer,
    fontWeight: '700',
    fontSize: 14,
  },
});

export default DiagnosisResultScreen;
