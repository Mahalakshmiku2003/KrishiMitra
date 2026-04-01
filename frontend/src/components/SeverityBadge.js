import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const SeverityBadge = ({ severity }) => {
  let backgroundColor = '#E8F5E9'; // Mild
  let textColor = '#2E7D32';

  if (severity === 'Moderate') {
    backgroundColor = '#FFF8E1';
    textColor = '#F9A825';
  } else if (severity === 'Severe') {
    backgroundColor = '#FFEBEE';
    textColor = '#C62828';
  }

  return (
    <View style={[styles.badge, { backgroundColor }]}>
      <Text style={[styles.text, { color: textColor }]}>{severity}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: 12,
    fontWeight: 'bold',
  },
});

export default SeverityBadge;
