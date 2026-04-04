import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ActivityIndicator,
  Animated,
  Dimensions,
  Image,
  Alert
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';

import { chatWithAssistant } from '../api/assistant';
import { theme } from '../theme';
import { saveAssistantChat, getAssistantChat } from '../utils/storage';
import Toast from 'react-native-toast-message';

const { width } = Dimensions.get('window');

const MessageBubble = ({ message, isUser }) => {
  const slideAnim = useRef(new Animated.Value(20)).current;
  const opacityAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideAnim, { toValue: 0, duration: 300, useNativeDriver: true }),
      Animated.timing(opacityAnim, { toValue: 1, duration: 300, useNativeDriver: true })
    ]).start();
  }, []);

  return (
    <Animated.View 
      style={[
        styles.messageWrapper, 
        isUser ? styles.userWrapper : styles.assistantWrapper,
        { transform: [{ translateY: slideAnim }], opacity: opacityAnim }
      ]}
    >
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        {!isUser && (
           <View style={styles.assistantAvatar}>
             <MaterialIcons name="psychology" size={16} color={theme.colors.onPrimary} />
           </View>
        )}
        <View style={[styles.bubbleContent, !isUser && { flexShrink: 1 }]}>
          {message.image && (
            <Image source={{ uri: message.image }} style={styles.messageImage} />
          )}
          <Text style={[styles.messageText, isUser ? styles.userText : styles.assistantText]}>
            {message.text || "I'm processing your request..."}
          </Text>
        </View>
      </View>
      <Text style={styles.timestamp}>{message.time}</Text>
    </Animated.View>
  );
};


const AssistantScreen = () => {
  const [input, setInput] = useState('');
  const [image, setImage] = useState(null);
  const [messages, setMessages] = useState([
    { id: '1', text: 'Namaste! I am KrishiMitra, your AI farming assistant. How can I help you today? 🌾', isUser: false, time: 'Now' }
  ]);
  const [loading, setLoading] = useState(false);
  const flatListRef = useRef();

  useEffect(() => {
    const loadHistory = async () => {
      const history = await getAssistantChat();
      if (history.length > 0) {
        setMessages(history);
      }
    };
    loadHistory();
  }, []);

  const handleSelectImage = async () => {
    const { status: cam } = await ImagePicker.requestCameraPermissionsAsync();
    const { status: lib } = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (cam !== 'granted' || lib !== 'granted') {
      Alert.alert('Permission Denied', 'KrishiMitra needs camera and gallery permissions.');
      return;
    }

    Alert.alert(
      'Attach Image',
      'Choose source',
      [
        { text: 'Camera', onPress: async () => {
          const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
          if (!result.canceled) setImage(result.assets[0].uri);
        }},
        { text: 'Gallery', onPress: async () => {
          const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
          if (!result.canceled) setImage(result.assets[0].uri);
        }},
        { text: 'Cancel', style: 'cancel' }
      ]
    );
  };

  const handleSend = async () => {
    if (!input.trim() && !image || loading) return;

    const userMsg = { 
      id: Date.now().toString(), 
      text: input, 
      image: image,
      isUser: true, 
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
    };
    
    setMessages(prev => {
      const updated = [...prev, userMsg];
      saveAssistantChat(updated);
      return updated;
    });
    
    const currentInput = input;
    const currentImage = image;
    
    setInput('');
    setImage(null);
    setLoading(true);

    try {
      let imageToUpload = null;
      if (currentImage) {
        const manipResult = await ImageManipulator.manipulateAsync(
          currentImage,
          [{ resize: { width: 1024 } }],
          { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG }
        );
        imageToUpload = manipResult.uri;
      }

      const response = await chatWithAssistant(currentInput || "Take a look at this crop.", 'demo_farmer', imageToUpload);
      const assistantMsg = {
        id: (Date.now() + 1).toString(),
        text: response.data.reply,
        isUser: false,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => {
        const updated = [...prev, assistantMsg];
        saveAssistantChat(updated);
        return updated;
      });
    } catch (err) {
      console.error(err);
      Toast.show({ type: 'error', text1: 'Connection Error', text2: 'Could not reach KrishiMitra' });
    } finally {
      setLoading(false);
    }
  };


  const renderQuickAction = (icon, label, callback) => (
    <TouchableOpacity style={styles.quickAction} onPress={() => setInput(label)}>
      <MaterialIcons name={icon} size={20} color={theme.colors.primary} />
      <Text style={styles.quickActionText}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerInfo}>
          <View style={styles.headerAvatar}>
            <MaterialIcons name="psychology" size={24} color={theme.colors.onPrimary} />
          </View>
          <View>
            <Text style={styles.headerTitle}>Kisan Assistant</Text>
            <View style={styles.statusRow}>
              <View style={styles.statusDot} />
              <Text style={styles.statusText}>AI Active</Text>
            </View>
          </View>
        </View>
        <TouchableOpacity style={styles.headerMore}>
          <MaterialIcons name="more-vert" size={24} color={theme.colors.onSurfaceVariant} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView 
        style={styles.container} 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 20}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          renderItem={({ item }) => <MessageBubble message={item} isUser={item.isUser} />}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          onLayout={() => flatListRef.current?.scrollToEnd({ animated: true })}
          ListHeaderComponent={() => (
            <View style={styles.quickActionsContainer}>
              {renderQuickAction('wb-sunny', 'Check Weather')}
              {renderQuickAction('trending-up', 'Mandi Prices')}
              {renderQuickAction('bug-report', 'Identify Disease')}
            </View>
          )}
        />

        {loading && (
          <View style={styles.thinkingContainer}>
            <ActivityIndicator size="small" color={theme.colors.primary} />
            <Text style={styles.thinkingText}>KrishiMitra is thinking...</Text>
          </View>
        )}

        <View style={styles.inputContainer}>
          {image && (
            <View style={styles.imagePreviewContainer}>
              <Image source={{ uri: image }} style={styles.imagePreview} />
              <TouchableOpacity style={styles.removeImageBtn} onPress={() => setImage(null)}>
                <MaterialIcons name="close" size={16} color={theme.colors.onPrimary} />
              </TouchableOpacity>
            </View>
          )}
          <View style={styles.inputWrapper}>
            <TouchableOpacity style={styles.attachBtn} onPress={handleSelectImage}>
              <MaterialIcons name="add-a-photo" size={24} color={theme.colors.primary} />
            </TouchableOpacity>
            <TextInput
              style={styles.textInput}
              placeholder={image ? "Describe the photo..." : "Ask anything (e.g. Tomato rates...)"}
              placeholderTextColor={theme.colors.outline}
              value={input}
              onChangeText={setInput}
              multiline
              blurOnSubmit={false}
              returnKeyType="send"
              onSubmitEditing={handleSend}
            />
            <TouchableOpacity 
              style={[styles.sendBtn, (!input.trim() && !image) && styles.disabledSend]} 
              onPress={handleSend}
              disabled={!input.trim() && !image}
            >
              <MaterialIcons name="send" size={20} color={theme.colors.onPrimary} />
            </TouchableOpacity>
          </View>
        </View>

      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.surface,
    marginBottom: Platform.OS === 'ios' ? 90 : 70, // Added to clear bottom navigator
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.surfaceVariant,
    backgroundColor: theme.colors.surface,
  },
  headerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: theme.colors.onSurface,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#4CAF50',
  },
  statusText: {
    fontSize: 10,
    color: theme.colors.onSurfaceVariant,
    fontWeight: '600',
  },
  container: {
    flex: 1,
  },
  messageList: {
    padding: 20,
    paddingBottom: Platform.OS === 'web' ? 20 : 40,
    flexGrow: 1,
  },
  messageWrapper: {
    marginBottom: 16,
    maxWidth: '85%',
  },
  userWrapper: {
    alignSelf: 'flex-end',
  },
  assistantWrapper: {
    alignSelf: 'flex-start',
  },
  bubble: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 20,
  },
  userBubble: {
    backgroundColor: theme.colors.primary,
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: theme.colors.surfaceContainerLow,
    borderBottomLeftRadius: 4,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  messageText: {
    fontSize: 15,
    lineHeight: 22,
  },
  userText: {
    color: theme.colors.onPrimary,
    fontWeight: '500',
  },
  assistantText: {
    color: theme.colors.onSurface,
    fontWeight: '400',
  },
  assistantAvatar: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: theme.colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  timestamp: {
    fontSize: 10,
    color: theme.colors.outline,
    marginTop: 4,
    marginHorizontal: 8,
  },
  quickActionsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 24,
  },
  quickAction: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.surfaceContainerHigh,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: theme.colors.surfaceVariant,
  },
  quickActionText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.onSurfaceVariant,
  },
  thinkingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 10,
    gap: 8,
  },
  thinkingText: {
    fontSize: 12,
    color: theme.colors.outline,
    fontStyle: 'italic',
  },
  inputContainer: {
    padding: 16,
    backgroundColor: theme.colors.surface,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: theme.colors.surfaceContainerLow,
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
    borderWidth: 1,
    borderColor: theme.colors.surfaceVariant,
  },
  textInput: {
    flex: 1,
    maxHeight: 100,
    fontSize: 15,
    color: theme.colors.onSurface,
    paddingTop: 8,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },
  disabledSend: {
    backgroundColor: theme.colors.surfaceVariant,
  },
  bubbleContent: {
    // flex: 1 removed to prevent vertical stretching in user bubbles
  },
  messageImage: {
    width: width * 0.6,
    height: 150,
    borderRadius: 12,
    marginBottom: 8,
    resizeMode: 'cover',
  },
  imagePreviewContainer: {
    padding: 8,
    paddingLeft: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  imagePreview: {
    width: 60,
    height: 60,
    borderRadius: 8,
  },
  removeImageBtn: {
    position: 'absolute',
    top: 0,
    left: 52,
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderRadius: 10,
    width: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  attachBtn: {
    padding: 4,
  }
});


export default AssistantScreen;
