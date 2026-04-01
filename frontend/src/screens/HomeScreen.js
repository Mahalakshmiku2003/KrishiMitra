import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, RefreshControl } from 'react-native';
import StatusBadge from '../components/StatusBadge';
import { checkHealth } from '../api/health';
import { getLastDiagnosis } from '../utils/storage';
import EmptyState from '../components/EmptyState';

const HomeScreen = ({ navigation }) => {
  const [serverStatus, setServerStatus] = useState('offline');
  const [recentDiagnosis, setRecentDiagnosis] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const res = await checkHealth();
      setServerStatus(res.status === 200 ? 'online' : 'offline');
    } catch (err) {
      setServerStatus('offline');
    }
    
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
    <ScrollView 
      style={styles.container} 
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#2E7D32']} />}
    >
      <Text style={styles.title}>KrishiMitra 🌾</Text>
      <Text style={styles.subtitle}>PhD-level farming intelligence in your pocket</Text>
      
      <StatusBadge status={serverStatus} />
      
      <View style={styles.actionRow}>
        <TouchableOpacity 
          style={[styles.button, styles.primaryButton]}
          onPress={() => navigation.navigate('Diagnose')}
        >
          <Text style={styles.buttonText}>🔍 Diagnose Crop</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.button, styles.accentButton]}
          onPress={() => navigation.navigate('Market')}
        >
          <Text style={[styles.buttonText, { color: '#333' }]}>💰 Market Prices</Text>
        </TouchableOpacity>
      </View>
      
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>Recent Activity</Text>
      </View>
      
      <View style={styles.card}>
        {recentDiagnosis ? (
          <View>
            <View style={styles.diagHeader}>
              <Text style={styles.diseaseName}>{recentDiagnosis.disease_name}</Text>
              <Text style={styles.dateText}>{recentDiagnosis.date ? new Date(recentDiagnosis.date).toLocaleDateString() : 'Today'}</Text>
            </View>
            <Text style={styles.cardText}>Confidence: {(recentDiagnosis.confidence * 100).toFixed(1)}%</Text>
            <Text style={[styles.cardText, { color: '#2E7D32', fontWeight: 'bold', marginTop: 4 }]}>
              Severity: {recentDiagnosis.severity || 'Normal'}
            </Text>
          </View>
        ) : (
          <EmptyState 
            icon="🌿" 
            title="No diagnosis yet" 
            subtitle="Take a photo of your crop to get started with AI diagnosis."
          />
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 24, paddingTop: 60 },
  title: { fontSize: 28, fontWeight: 'bold', color: '#2E7D32', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#2E7D32', opacity: 0.8, marginBottom: 24 },
  actionRow: { marginTop: 10 },
  button: {
    width: '100%',
    height: 56,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    elevation: 2,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.2, shadowRadius: 2,
  },
  primaryButton: { backgroundColor: '#2E7D32' },
  accentButton: { backgroundColor: '#F9A825' },
  buttonText: { fontSize: 16, fontWeight: 'bold', color: '#FFFFFF' },
  cardHeader: { marginTop: 10, marginBottom: 12 },
  cardTitle: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  card: { 
    backgroundColor: '#FFFFFF', 
    borderRadius: 12, 
    padding: 16, 
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 10, elevation: 2 
  },
  diagHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 12, borderBottomWidth: 1, borderBottomColor: '#F5F5F5', paddingBottom: 8 },
  diseaseName: { fontSize: 18, fontWeight: 'bold', color: '#2E7D32' },
  dateText: { fontSize: 12, color: '#9E9E9E' },
  cardText: { fontSize: 14, color: '#666' }
});

export default HomeScreen;
