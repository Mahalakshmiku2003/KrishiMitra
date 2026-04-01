import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Modal } from 'react-native';

const LoadingOverlay = ({ visible, message }) => {
  return (
    <Modal transparent visible={visible} animationType="fade">
      <View style={styles.overlay}>
        <View style={styles.container}>
          <ActivityIndicator size="large" color="#2E7D32" />
          {message && <Text style={styles.message}>{message}</Text>}
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  container: {
    backgroundColor: '#FFFFFF',
    padding: 30,
    borderRadius: 12,
    alignItems: 'center',
    width: '80%',
  },
  message: {
    marginTop: 15,
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
    textAlign: 'center',
  },
});

export default LoadingOverlay;
