import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Image, SafeAreaView, Platform } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { checkHealth } from '../api/health';
import { getLastDiagnosis } from '../utils/storage';
import EmptyState from '../components/EmptyState';
import { theme } from '../theme';

const HomeScreen = ({ navigation }) => {
  const [serverStatus, setServerStatus] = useState('offline');
  const [recentDiagnosis, setRecentDiagnosis] = fallbackData();
  const [refreshing, setRefreshing] = useState(false);

  function fallbackData() { return useState(null); }

  const fetchData = async () => {
    try {
      const res = await checkHealth();
      setServerStatus(res.status === 200 ? 'online' : 'offline');
    } catch (err) {
      setServerStatus('offline');
    }
    
    // Keeping storage logic
    const diag = await getLastDiagnosis();
    setRecentDiagnosis(diag);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Top Navigation Anchor */}
      <View style={styles.header}>
        <View style={styles.headerLogoContainer}>
          <MaterialIcons name="local-florist" size={24} color={theme.colors.primary} />
          <Text style={styles.headerLogoText}>KrishiMitra</Text>
        </View>
        <MaterialIcons name="cloud" size={24} color={theme.colors.primaryContainer} />
      </View>

      <ScrollView 
        style={styles.container} 
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[theme.colors.primary]} />}
      >
        {/* Hero Identity Section */}
        <View style={styles.heroSection}>
          <View style={styles.heroPretitleContainer}>
            <MaterialIcons name="grass" size={16} color={theme.colors.tertiary} />
            <Text style={styles.heroPretitle}>THE DIGITAL AGRONOMIST</Text>
          </View>
          <Text style={styles.heroSubtitle}>PhD-level farming intelligence in your pocket</Text>
        </View>

        {/* Weather Strip Card */}
        <View style={styles.weatherCard}>
          <View style={styles.weatherLeft}>
            <View style={styles.weatherIconContainer}>
              <MaterialIcons name="wb-sunny" size={28} color={theme.colors.onTertiaryFixed} />
            </View>
            <View>
              <Text style={styles.weatherTemp}>24°C</Text>
              <Text style={styles.weatherCity}>Karnataka, IN</Text>
            </View>
          </View>
          <View style={styles.weatherRight}>
            <View style={styles.idealStateBadge}>
              <View style={styles.idealStateDot} />
              <Text style={styles.idealStateText}>MORNING WEATHER</Text>
            </View>
            <Text style={styles.weatherSubtext}>Cool morning, perfect for irrigation</Text>
          </View>
          <TouchableOpacity onPress={() => navigation.navigate('Outbreak')} style={styles.weatherDetailBtn}>
             <MaterialIcons name="chevron-right" size={24} color={theme.colors.primary} />
          </TouchableOpacity>
        </View>

        {/* Server Status Pill */}
        <View style={styles.statusContainer}>
          <View style={styles.statusPill}>
            <View style={[styles.statusDot, { backgroundColor: serverStatus === 'online' ? theme.colors.primaryContainer : theme.colors.error }]} />
            <Text style={styles.statusText}>SERVER {serverStatus.toUpperCase()}</Text>
          </View>
        </View>

        {/* Primary Actions */}
        <View style={styles.actionGrid}>
          <TouchableOpacity 
            style={styles.primaryActionButton}
            onPress={() => navigation.navigate('Diagnose')}
            activeOpacity={0.9}
          >
            <View style={styles.actionRowPrimary}>
              <MaterialIcons name="photo-camera" size={24} color={theme.colors.onPrimary} />
              <Text style={styles.primaryActionText}>Diagnose My Crop</Text>
            </View>
            <MaterialIcons name="arrow-forward-ios" size={18} color={theme.colors.onPrimary} />
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.secondaryActionButton}
            onPress={() => navigation.navigate('Market')}
            activeOpacity={0.9}
          >
            <View style={styles.actionRowPrimary}>
              <MaterialIcons name="currency-rupee" size={24} color={theme.colors.onTertiary} />
              <Text style={styles.secondaryActionText}>Check Market Prices</Text>
            </View>
            <MaterialIcons name="arrow-forward-ios" size={18} color={theme.colors.onTertiary} />
          </TouchableOpacity>

          <TouchableOpacity 
            style={[styles.primaryActionButton, { backgroundColor: theme.colors.tertiaryContainer }]}
            onPress={() => navigation.navigate('Assistant')}
            activeOpacity={0.9}
          >
            <View style={styles.actionRowPrimary}>
              <MaterialIcons name="psychology" size={24} color={theme.colors.onTertiaryContainer} />
              <Text style={[styles.primaryActionText, { color: theme.colors.onTertiaryContainer }]}>AI Kisan Assistant</Text>
            </View>
            <MaterialIcons name="arrow-forward-ios" size={18} color={theme.colors.onTertiaryContainer} />
          </TouchableOpacity>
        </View>

        {/* Recent Activity */}
        <View style={styles.recentActivitySection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Recent Activity</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Outbreak')}>
              <Text style={styles.seeAllText}>VIEW DETAILS</Text>
            </TouchableOpacity>
          </View>

          {recentDiagnosis ? (
            <View style={styles.activityCard}>
              <View style={styles.activityImageContainer}>
                {recentDiagnosis.image_uri ? (
                  <Image source={{ uri: recentDiagnosis.image_uri }} style={styles.activityImage} />
                ) : (
                  <View style={[styles.activityImage, { backgroundColor: theme.colors.surfaceContainerHighest }]} />
                )}
                <View style={[styles.activityBadge, { backgroundColor: recentDiagnosis.severity === 'High' ? theme.colors.error : theme.colors.secondary }]}>
                  <Text style={styles.activityBadgeText}>{recentDiagnosis.severity || 'Normal'}</Text>
                </View>
              </View>
              <View style={styles.activityCardBody}>
                <View style={styles.activityBodyHeader}>
                  <View>
                    <Text style={styles.activityTitle}>{recentDiagnosis.disease_name}</Text>
                    <Text style={styles.activitySubtitle}>Confidence: {(recentDiagnosis.confidence * 100).toFixed(1)}%</Text>
                  </View>
                  <Text style={styles.activityDate}>{recentDiagnosis.date ? new Date(recentDiagnosis.date).toLocaleDateString() : 'TODAY'}</Text>
                </View>
                <View style={styles.activityFooterRow}>
                  <View style={styles.activityFooterLeft}>
                    <MaterialIcons name="medical-services" size={14} color={theme.colors.primary} />
                    <Text style={styles.activityFooterText}>Treatment Plan Ready</Text>
                  </View>
                  <TouchableOpacity 
                    onPress={() => {
                      if (recentDiagnosis && recentDiagnosis.image_uri) {
                        navigation.navigate('Diagnose', { 
                          screen: 'DiagnosisResult', 
                          initial: false,
                          params: { result: { 
                            status: 'cached', 
                            detections: [{ 
                              disease: recentDiagnosis.disease_name || 'Unknown', 
                              confidence: recentDiagnosis.confidence || 0, 
                              severity: recentDiagnosis.severity || 'Medium' 
                            }], 
                            annotated_image: recentDiagnosis.image_uri.includes(',') ? 
                              recentDiagnosis.image_uri.split(',')[1] : 
                              recentDiagnosis.image_uri
                          }} 
                        });
                      }
                    }} 
                    style={styles.viewDetailsBtn}
                  >
                    <Text style={styles.viewDetailsText}>VIEW DETAILS</Text>
                    <MaterialIcons name="chevron-right" size={14} color={theme.colors.onSurfaceVariant} />
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          ) : (
             <EmptyState 
              icon="spa" 
              title="No diagnosis yet" 
              subtitle="Take a photo of your crop to get started with AI diagnosis."
            />
          )}
        </View>

        {/* Quick Stats Bento Grid */}
        <View style={styles.bentoGrid}>
          <TouchableOpacity 
            onPress={() => navigation.navigate('Diagnose')}
            style={styles.bentoItemSmall}
          >
            <MaterialIcons name="analytics" size={24} color={theme.colors.primary} />
            <View style={styles.bentoTextGroup}>
              <Text style={styles.bentoVal}>2</Text>
              <Text style={styles.bentoLabel}>DIAGNOSES TODAY</Text>
            </View>
          </TouchableOpacity>
          
          <TouchableOpacity 
            onPress={() => navigation.navigate('Market')}
            style={styles.bentoItemSmall}
          >
            <MaterialIcons name="trending-up" size={24} color={theme.colors.tertiary} />
            <View style={styles.bentoTextGroup}>
              <Text style={styles.bentoVal}>₹3200</Text>
              <Text style={styles.bentoLabel}>AVG TOMATO/QUINTAL</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity 
            onPress={() => navigation.navigate('Outbreak')}
            style={styles.bentoItemLarge}
          >
            <View style={styles.bentoLargeTextGroup}>
              <Text style={styles.bentoLargeLabel}>WEATHER RISK</Text>
              <Text style={styles.bentoLargeVal}>Very Low</Text>
            </View>
            <View style={styles.bentoIconBg}>
              <MaterialIcons name="verified-user" size={36} color={theme.colors.onPrimaryContainer} />
            </View>
          </TouchableOpacity>
        </View>
        
        {/* Padding for bottom tab nav */}
        <View style={{height: 100}} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.surface,
    paddingTop: Platform.OS === 'android' ? 25 : 0,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    backgroundColor: theme.colors.surfaceContainerLow,
    zIndex: 10,
  },
  headerLogoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerLogoText: {
    fontSize: 24,
    fontWeight: '700',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  container: {
    flex: 1,
    backgroundColor: theme.colors.surface,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 24,
    gap: 32,
  },
  heroSection: {
    gap: 4,
  },
  heroPretitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  heroPretitle: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.tertiary,
    letterSpacing: 2,
    ...theme.typography.label,
  },
  heroSubtitle: {
    fontSize: 14,
    color: theme.colors.onSurfaceVariant,
    opacity: 0.8,
    lineHeight: 22,
  },
  weatherCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 24,
    padding: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.04,
    shadowRadius: 24,
    elevation: 2,
    marginBottom: -10, // overlap effect
  },
  weatherLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  weatherIconContainer: {
    backgroundColor: theme.colors.tertiaryFixed,
    padding: 12,
    borderRadius: 16,
  },
  weatherTemp: {
    fontSize: 24,
    fontWeight: '700',
    color: theme.colors.onSurface,
  },
  weatherCity: {
    fontSize: 12,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
  },
  weatherRight: {
    alignItems: 'flex-end',
  },
  idealStateBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 4,
    backgroundColor: 'rgba(46, 125, 50, 0.1)',
    borderRadius: 999,
    marginBottom: 4,
  },
  idealStateDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.primary,
  },
  idealStateText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.primary,
    ...theme.typography.label,
  },
  weatherDetailBtn: {
    padding: 4,
  },
  weatherSubtext: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.primary,
  },
  statusContainer: {
    alignItems: 'center',
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 6,
    backgroundColor: theme.colors.surfaceContainerHighest,
    borderRadius: 999,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
    letterSpacing: 0.5,
    ...theme.typography.label,
  },
  actionGrid: {
    gap: 16,
  },
  primaryActionButton: {
    width: '100%',
    backgroundColor: theme.colors.primary,
    paddingVertical: 20,
    paddingHorizontal: 24,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  secondaryActionButton: {
    width: '100%',
    backgroundColor: theme.colors.tertiary,
    paddingVertical: 20,
    paddingHorizontal: 24,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  actionRowPrimary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  primaryActionText: {
    color: theme.colors.onPrimary,
    fontSize: 18,
    fontWeight: '700',
  },
  secondaryActionText: {
    color: theme.colors.onTertiary,
    fontSize: 18,
    fontWeight: '700',
  },
  recentActivitySection: {
    gap: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: theme.colors.onSurface,
    letterSpacing: -0.5,
  },
  seeAllText: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.primary,
    letterSpacing: 1,
    ...theme.typography.label,
  },
  activityCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(191, 202, 186, 0.2)', // outlineVariant approx
  },
  activityImageContainer: {
    height: 128,
    width: '100%',
    position: 'relative',
  },
  activityImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  activityBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  activityBadgeText: {
    color: theme.colors.onError,
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  activityCardBody: {
    padding: 16,
    gap: 12,
  },
  activityBodyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  activityTitle: {
    fontSize: 16,
    fontWeight: '700',
    lineHeight: 20,
  },
  activitySubtitle: {
    fontSize: 12,
    color: theme.colors.onSurfaceVariant,
    marginTop: 2,
  },
  activityDate: {
    fontSize: 10,
    color: theme.colors.onSurfaceVariant,
    ...theme.typography.label,
  },
  activityFooterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 8,
  },
  activityFooterLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  activityFooterText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.primary,
  },
  viewDetailsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewDetailsText: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    ...theme.typography.label,
  },
  bentoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  bentoItemSmall: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: theme.colors.surfaceContainerLow,
    padding: 16,
    borderRadius: 24,
    gap: 8,
  },
  bentoTextGroup: {
    marginTop: 4,
  },
  bentoVal: {
    fontSize: 32,
    fontWeight: '800',
    color: theme.colors.onSurface,
    lineHeight: 38,
  },
  bentoLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    letterSpacing: 0.5,
    ...theme.typography.label,
  },
  bentoItemLarge: {
    width: '100%',
    backgroundColor: theme.colors.primaryContainer,
    padding: 20,
    borderRadius: 24,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  bentoLargeTextGroup: {
    gap: 4,
  },
  bentoLargeLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: theme.colors.onPrimaryContainer,
    opacity: 0.8,
    letterSpacing: 1,
    ...theme.typography.label,
  },
  bentoLargeVal: {
    fontSize: 24,
    fontWeight: '700',
    color: theme.colors.onPrimaryContainer,
  },
  bentoIconBg: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    padding: 12,
    borderRadius: 999,
  }
});

export default HomeScreen;

