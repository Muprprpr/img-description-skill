package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"image"
	"image/draw" // 引入绘图包
	"image/jpeg"
	_ "image/png"
	"log"
	"math/bits"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
) // <--- 之前这里少了反括号

// --- 阈值定义 ---
const (
	ThresholdWeak  = 24 // L3: 弱相关
	ThresholdHigh  = 9  // L2: 高度相似
	ThresholdExact = 1  // L1: 完全重合
	CollageSize    = 1024
)

// --- 输出数据结构 (三层嵌套) ---

// Level 1: 最底层的精确组
type ExactGroup struct {
	Count  int      `json:"count"`
	Images []string `json:"images"`
}

// Level 2: 中层的高度相似组
type HighSimGroup struct {
	SubLeader string       `json:"sub_leader_path"`
	Count     int          `json:"total_images"`
	Variants  []ExactGroup `json:"exact_variants"`
}

// Level 3: 顶层的弱相关组
type WeakRelGroup struct {
	GroupID     int            `json:"group_id"`
	CollagePath string         `json:"l3_collage_path"`
	Count       int            `json:"total_images"`
	SubGroups   []HighSimGroup `json:"high_sim_subgroups"`
}

// 内部处理用的节点
type Node struct {
	ID   int
	Path string
	Hash uint64
}

func main() {
	dirPtr := flag.String("dir", ".", "图片文件夹路径")
	outputDirPtr := flag.String("out", "./collages", "拼图输出文件夹")
	flag.Parse()

	// 创建拼图输出目录
	if _, err := os.Stat(*outputDirPtr); os.IsNotExist(err) {
		os.Mkdir(*outputDirPtr, os.ModePerm)
	}
	fmt.Printf(">> [智能聚类+自动拼图] 扫描: %s\n", *dirPtr)

	start := time.Now()

	// 1. 加载图片
	nodes, err := loadImages(*dirPtr)
	if err != nil {
		log.Fatal(err)
	}
	if len(nodes) == 0 {
		return
	}

	// 2. 执行聚类 & 生成拼图
	result := performHierarchicalClustering(nodes, *outputDirPtr)

	// 3. 输出 JSON
	outputJSON(result)
	fmt.Printf("\n>> 全部完成，耗时: %v\n", time.Since(start))
}

// --- 核心聚类逻辑 ---

func performHierarchicalClustering(nodes []Node, outDir string) []WeakRelGroup {
	// Step 1: L3 聚类 (Union-Find)
	weakClusters := clusterByUnionFind(nodes, ThresholdWeak)
	var finalOutput []WeakRelGroup
	var mutex sync.Mutex
	var wg sync.WaitGroup

	for i, clusterNodes := range weakClusters {
		// 过滤掉只有 1 张图且没有关联的孤岛
		if len(clusterNodes) < 2 {
			continue
		}

		wg.Add(1)
		go func(idx int, cNodes []Node) {
			defer wg.Done()

			// --- 生成拼图 ---
			var collageInputs []string
			limit := 4
			if len(cNodes) < 4 {
				limit = len(cNodes)
			}
			for k := 0; k < limit; k++ {
				collageInputs = append(collageInputs, cNodes[k].Path)
			}

			collageFilename := filepath.Join(outDir, fmt.Sprintf("group_%d_l3_collage.jpg", idx+1))
			// 如果拼图生成出错，仅打印日志，不中断流程
			if err := GenerateCollage(collageInputs, collageFilename); err != nil {
				fmt.Printf("拼图警告: %v\n", err)
			}

			// --- L2 & L1 聚类 ---
			highClusters := clusterGreedy(cNodes, ThresholdHigh)
			var highGroups []HighSimGroup

			for _, subNodes := range highClusters {
				exactClusters := clusterGreedy(subNodes, ThresholdExact)
				var exactGroups []ExactGroup
				for _, exactNodes := range exactClusters {
					var paths []string
					for _, n := range exactNodes {
						paths = append(paths, n.Path)
					}
					exactGroups = append(exactGroups, ExactGroup{
						Count:  len(paths),
						Images: paths,
					})
				}

				highGroups = append(highGroups, HighSimGroup{
					SubLeader: subNodes[0].Path,
					Count:     len(subNodes),
					Variants:  exactGroups,
				})
			}

			mutex.Lock()
			finalOutput = append(finalOutput, WeakRelGroup{
				GroupID:     idx + 1,
				CollagePath: collageFilename,
				Count:       len(cNodes),
				SubGroups:   highGroups,
			})
			mutex.Unlock()
		}(i, clusterNodes)
	}
	wg.Wait()
	return finalOutput
}

// ---------------------------------------------------------
//  拼图生成器
// ---------------------------------------------------------

func GenerateCollage(imagePaths []string, outPath string) error {
	canvasSize := 1024
	cellSize := canvasSize / 2
	canvas := image.NewRGBA(image.Rect(0, 0, canvasSize, canvasSize))

	offsets := []image.Point{
		{0, 0}, {cellSize, 0},
		{0, cellSize}, {cellSize, cellSize},
	}

	for i, path := range imagePaths {
		if i >= 4 {
			break
		}

		file, err := os.Open(path)
		if err != nil {
			continue
		}
		img, _, err := image.Decode(file)
		file.Close()
		if err != nil {
			continue
		}

		// 缩放图片到 512x512 (RGB模式)
		resized := resizeColorImage(img, cellSize, cellSize)

		drawRect := image.Rect(offsets[i].X, offsets[i].Y, offsets[i].X+cellSize, offsets[i].Y+cellSize)
		draw.Draw(canvas, drawRect, resized, image.Point{0, 0}, draw.Over)
	}

	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()

	return jpeg.Encode(outFile, canvas, &jpeg.Options{Quality: 80})
}

// resizeColorImage 彩色缩放 (你之前遗漏了这个函数)
func resizeColorImage(img image.Image, width, height int) image.Image {
	bounds := img.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, width, height))
	srcW, srcH := bounds.Dx(), bounds.Dy()

	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			srcX := x * srcW / width
			srcY := y * srcH / height
			dst.Set(x, y, img.At(bounds.Min.X+srcX, bounds.Min.Y+srcY))
		}
	}
	return dst
}

// ---------------------------------------------------------
//  基础聚类算法
// ---------------------------------------------------------

func clusterByUnionFind(nodes []Node, threshold int) [][]Node {
	n := len(nodes)
	uf := NewUnionFind(n)

	for i := 0; i < n; i++ {
		for j := i + 1; j < n; j++ {
			if HammingDistance(nodes[i].Hash, nodes[j].Hash) <= threshold {
				uf.Union(i, j)
			}
		}
	}

	groups := make(map[int][]Node)
	for i := 0; i < n; i++ {
		root := uf.Find(i)
		groups[root] = append(groups[root], nodes[i])
	}

	var result [][]Node
	for _, g := range groups {
		result = append(result, g)
	}
	return result
}

func clusterGreedy(nodes []Node, threshold int) [][]Node {
	var result [][]Node
	visited := make([]bool, len(nodes))

	for i := 0; i < len(nodes); i++ {
		if visited[i] {
			continue
		}
		var currentGroup []Node
		currentGroup = append(currentGroup, nodes[i])
		visited[i] = true

		for j := i + 1; j < len(nodes); j++ {
			if !visited[j] {
				dist := HammingDistance(nodes[i].Hash, nodes[j].Hash)
				if dist <= threshold {
					currentGroup = append(currentGroup, nodes[j])
					visited[j] = true
				}
			}
		}
		result = append(result, currentGroup)
	}
	return result
}

// --- UnionFind ---
type UnionFind struct {
	parent []int
}

func NewUnionFind(n int) *UnionFind {
	parent := make([]int, n)
	for i := 0; i < n; i++ {
		parent[i] = i
	}
	return &UnionFind{parent: parent}
}

func (uf *UnionFind) Find(i int) int {
	if uf.parent[i] != i {
		uf.parent[i] = uf.Find(uf.parent[i])
	}
	return uf.parent[i]
}

func (uf *UnionFind) Union(i, j int) {
	rootI, rootJ := uf.Find(i), uf.Find(j)
	if rootI != rootJ {
		if rootI < rootJ {
			uf.parent[rootJ] = rootI
		} else {
			uf.parent[rootI] = rootJ
		}
	}
}

// --- 基础图像处理 (Hash) ---

func ComputeDHash(imgPath string) (uint64, error) {
	file, err := os.Open(imgPath)
	if err != nil {
		return 0, err
	}
	defer file.Close()
	img, _, err := image.Decode(file)
	if err != nil {
		return 0, err
	}
	// 这里用灰度缩放来算Hash，效率高
	resized := resizeGrayImage(img, 9, 8)
	var hash uint64
	for y := 0; y < 8; y++ {
		for x := 0; x < 8; x++ {
			if getGrayscale(resized, x, y) > getGrayscale(resized, x+1, y) {
				hash |= 1 << uint(y*8+x)
			}
		}
	}
	return hash, nil
}

func HammingDistance(h1, h2 uint64) int {
	return bits.OnesCount64(h1 ^ h2)
}

// resizeGrayImage: 专门给 Hash 用的灰度缩放
func resizeGrayImage(img image.Image, width, height int) image.Image {
	bounds := img.Bounds()
	dst := image.NewGray(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			srcX := x * bounds.Dx() / width
			srcY := y * bounds.Dy() / height
			dst.Set(x, y, img.At(bounds.Min.X+srcX, bounds.Min.Y+srcY))
		}
	}
	return dst
}

func getGrayscale(img image.Image, x, y int) uint8 {
	c := img.At(x, y)
	r, g, b, _ := c.RGBA()
	return uint8((299*uint32(r) + 587*uint32(g) + 114*uint32(b) + 500) / 1000 >> 8)
}

func loadImages(dir string) ([]Node, error) {
	var nodes []Node
	var mutex sync.Mutex
	var wg sync.WaitGroup

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if ext != ".jpg" && ext != ".jpeg" && ext != ".png" {
			return nil
		}

		wg.Add(1)
		go func(p string) {
			defer wg.Done()
			h, err := ComputeDHash(p)
			if err == nil {
				mutex.Lock()
				nodes = append(nodes, Node{Path: p, Hash: h})
				mutex.Unlock()
			}
		}(path)
		return nil
	})
	wg.Wait()
	for i := range nodes {
		nodes[i].ID = i
	}
	return nodes, err
}

func outputJSON(data interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	fmt.Println("\n--------- 嵌套聚类分析报告 ---------")
	if err := enc.Encode(data); err != nil {
		fmt.Println("JSON 编码失败:", err)
	}
}
