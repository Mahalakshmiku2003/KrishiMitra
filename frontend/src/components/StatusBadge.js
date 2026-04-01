import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const StatusBadge = ({ status }) => {
  const isOnline = status === 'online';
  
  return (
    <View style={styles.container}>
      <View style={[styles.dot, isOnline ? styles.onlineDot : styles.offlineDot]} />
      <Text style={styles.text}>
        {isOnline ? 'Server connected' : 'Server offline'}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
    alignSelf: 'flex-start',
    marginBottom: 20
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8
  },
  onlineDot: {
    backgroundColor: '#2E7D32'
  },
  offlineDot: {
    backgroundColor: '#D32F2F'
  },
  text: {
    fontSize: 14,
    color: '#333',
    fontWeight: '500'
  }
});

export default StatusBadge;
